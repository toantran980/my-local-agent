GPU monitoring

The gpu_status tool reports how much VRAM each loaded model is using and how long it stays resident. Run make gpu to see the same numbers. Use it to spot a model that was evicted to the CPU after another model loaded.
