import { analyze } from './engine.js';

self.onmessage = (e) => {
  const { id, data, options } = e.data;
  try {
    const t0 = performance.now();
    const result = analyze(data, options);
    result.ms = Math.round(performance.now() - t0);
    self.postMessage({ id, result });
  } catch (err) {
    self.postMessage({ id, error: String(err && err.stack || err) });
  }
};
