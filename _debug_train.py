import sys, traceback, io
sys.path.insert(0, '.')
buf = io.StringIO()
try:
    import pokemon_price_monitor as pm
    buf.write('=== Train USD ===\n')
    m = pm.train_model(max_sets=50)
    buf.write(f'USD trained: {m is not None}\n')
except Exception as e:
    traceback.print_exc(file=buf)
    buf.write(f'ERROR: {e}\n')

# Write all output to file
with open('_debug_out.txt', 'w') as f:
    f.write(buf.getvalue())
