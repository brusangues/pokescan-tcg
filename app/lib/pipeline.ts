
// Singleton pattern for the pipeline
class PipelineSingleton {
  static task = 'feature-extraction';
  static model = 'Xenova/clip-vit-base-patch32';
  static instance: any = null;

  static async getInstance(progressCallback: (data: any) => void = () => {}) {
    if (typeof window === 'undefined') {
      return null;
    }

    if (this.instance === null) {
      const { pipeline, env } = await import('@xenova/transformers');
      
      // Configure environment
      env.allowLocalModels = false;
      env.useBrowserCache = true;

      this.instance = pipeline(this.task as any, this.model, { progress_callback: progressCallback });
    }
    return this.instance;
  }
}

export default PipelineSingleton;
