window.OpenCollection = class OpenCollection {
  constructor(id) {
    const target = document.getElementById(id);
    if (target) target.textContent = 'ok';
  }
};
