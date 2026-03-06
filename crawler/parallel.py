import os
import gc
import signal
import time
import traceback
import multiprocessing as mp
from functools import partial
from tqdm import tqdm
from IPython.utils import io
import os


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        delta_s = te - ts
        delta_min = delta_s / 60
        print(f"{method.__name__} took: {delta_s:0.1f} s ({delta_min:0.1f} min)")
        return result

    return timed


def init_worker(active_processes):
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ignore Ctrl+C in workers
    active_processes.append(mp.current_process().pid)


def wrapper(func, silent=True, kwargs={}):
    try:
        if silent:
            with io.capture_output() as captured:
                results = func(**kwargs)
        else:
            results = func(**kwargs)
    except Exception as e:
        if silent:
            captured.show()
            print(captured.stdout, captured.stderr)
        traceback.print_exc()
        pid = os.getpid()
        results = None
        print(f"\nERROR: {pid=} {e=}")
    gc.collect()
    return results


@timeit
def parallel_processing(
    func: callable,
    kwargs_list: list,
    num_workers: int = 8,
    silent: bool = True,
    timeout: int = 10,
    retry: int = 1,
    sleep: int = 1,
):
    """Parallel processing v2 using a worker pool with progress tracking and active process check.
    Args:
        func (callable): The function to be executed in parallel.
        kwargs_list (list): A list of keyword arguments for the function.
        num_workers (int, optional): The number of worker processes. Defaults to 8.
        silent (bool, optional): Whether to suppress prints. Defaults to True.
        timeout (int, optional): Timeout of each job in seconds. Defaults to 10.
        retry (int, optional): Max number of retries of each job. Defaults to 1.
        sleep (int, optional): Sleep time in between process checks in seconds. Defaults to 1.
    """
    active_processes = mp.Manager().list()
    init_worker_partial = partial(init_worker, active_processes)
    func_partial = partial(wrapper, func, silent)

    with mp.Pool(processes=num_workers, initializer=init_worker_partial) as pool:
        with tqdm(total=len(kwargs_list), desc="Processing Jobs", unit="job") as pbar:
            # Inicialização dos jobs
            results = [None for _ in kwargs_list]
            async_results = [pool.apply_async(func_partial, (k,)) for k in kwargs_list]
            async_info = {
                i: {"async_result": r, "start": None, "retry_count": 0, "kwargs": k}
                for i, (k, r) in enumerate(zip(kwargs_list, async_results))
            }
            # Loop de checagem de processos e resultados
            while async_info:
                # list_processes = list(active_processes)
                # print(f"{len(async_info)=} {len(list_processes)=} {list_processes=}")
                checked_pids = False
                for i, info in async_info.items():
                    async_result = info["async_result"]
                    kwargs = info["kwargs"]
                    if async_result.ready():
                        try:
                            results[i] = async_result.get()
                            pbar.update()
                        except Exception as e:
                            print(f"\nERROR getting  async result: {i=} {kwargs=} {e=}")
                            pbar.update()
                        finally:
                            async_info.pop(i)
                            break
                    # Se o índice do job for o primeiro dos restantes, começa contagem
                    min_index_result_left = list(async_info.keys())[0]
                    if info["start"] is None and i == min_index_result_left:
                        info["start"] = time.time()
                    # Se o tempo de timeout for atingido, faz o retry
                    elif info["start"] and (time.time() - info["start"] >= timeout):
                        retry_count = async_info[i]["retry_count"]
                        print(f"\nTimeout: {i=} {retry_count=}/{retry} {kwargs=}")
                        if retry_count < retry:
                            print(f"Retrying: {i=}")
                            retry_count += 1
                            async_info[i]["async_result"] = pool.apply_async(
                                func_partial, (kwargs,)
                            )
                            async_info[i]["start"] = None
                            async_info[i]["retry_count"] = retry_count
                        else:
                            print(f"\nRetry limit reached: {i=}")
                            async_info.pop(i)
                        break
                    # Procura por processos mortos
                    if not checked_pids:
                        checked_pids = True
                        for pid in list(active_processes):
                            if not any(p.pid == pid for p in mp.active_children()):
                                print(f"\nERROR: Process {pid} has died.")
                                active_processes.remove(pid)
                        time.sleep(sleep)
                        pbar.refresh()

    return results


@timeit
def sequential_processing(
    func: callable,
    kwargs_list: list,
    silent: bool = True,
    retry: int = 1,
):
    results = []
    for kwargs in tqdm(kwargs_list, desc="Processing Jobs", unit="job"):
        try:
            result = wrapper(func, silent, kwargs)
            results.append(result)
        except Exception as e:
            print(f"\nERROR processing job: {kwargs=} {e=}")
            if retry > 0:
                print(f"Retrying: {kwargs=}")
                kwargs_list.append(kwargs)  # Re-adiciona o job para tentar novamente
    return results


def process_function(result, sleep):
    time.sleep(sleep)
    return result

if __name__ == "__main__":
    kwargs_list = [{"result": 1, "sleep": 1} for i in range(20)]
    print(kwargs_list)

    print("Deve demorar menos que 20 segundos:")
    results = parallel_processing(
        func=process_function,
        kwargs_list=kwargs_list,
        num_workers=4,
        silent=False,
        timeout=10000,
        retry=0,
        sleep=0.2,
    )
    print()
    print(f"{len(results)=} {results=}")

    print("Deve demorar 20 segundos:")
    results = sequential_processing(
        func=process_function,
        kwargs_list=kwargs_list,
        silent=False,
        retry=0,
    )
    print()
    print(f"{len(results)=} {results=}")
