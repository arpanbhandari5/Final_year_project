export const animate = (...args) => {
  if (window.Motion && typeof window.Motion.animate === "function") {
    return window.Motion.animate(...args);
  }
  const [target, keyframes, options] = args;
  return target.animate(keyframes, options);
};
