"use strict";
(() => {
  function createBridge({parentOrigin = "", embedded = false, send = () => {}} = {}) {
    const match = /^http:\/\/127\.0\.0\.1:([1-9][0-9]{0,4})$/.exec(parentOrigin);
    const bound = embedded && !!match && Number(match[1]) <= 65535;
    let dirty = false, ready = false;
    const operations = new Set();
    const snapshot = () => ({dirty, busy:operations.size > 0});
    function notify(type = "pasarela:state") {
      if (bound && ready) send({type, ...snapshot()}, parentOrigin);
    }
    return {
      embedded:bound,
      snapshot,
      setDirty(value) {value = !!value;if (dirty !== value) {dirty = value;notify();}},
      setBusy(operation, value) {
        const before = operations.size > 0;
        if (value) operations.add(operation);else operations.delete(operation);
        if (before !== (operations.size > 0)) notify();
      },
      ready() {if (!ready) {ready = true;notify("pasarela:ready");}},
      shouldWarn() {return dirty || operations.size > 0;}
    };
  }
  if (typeof module !== "undefined" && module.exports) module.exports = {createBridge};
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const bridge = createBridge({
    parentOrigin:document.querySelector('meta[name="pasarela-parent-origin"]')?.content || "",
    embedded:window.parent !== window,
    send:(payload, origin) => window.parent.postMessage(payload, origin)
  });
  window.PasarelaIntegration = bridge;
  document.body.classList.toggle("embedded", bridge.embedded);
  window.addEventListener("beforeunload", event => {
    if (!bridge.shouldWarn()) return;
    event.preventDefault();
    event.returnValue = "";
  });
})();
