(() => {
  "use strict";

  const root = document.documentElement;
  const toolId = document.body.dataset.toolId || document.title || location.pathname;
  const storageKey = `brand-house-tool:${toolId}`;
  const fields = () => Array.from(document.querySelectorAll("input, select, textarea"))
    .filter((element) => element.name || element.dataset.field);
  const statusNode = document.querySelector("[data-save-status]");

  function fieldKey(element, index) {
    return element.dataset.field || element.name || `field-${index}`;
  }

  function readValue(element) {
    if (element.type === "checkbox" || element.type === "radio") return element.checked;
    return element.value;
  }

  function writeValue(element, value) {
    if (element.type === "checkbox" || element.type === "radio") {
      element.checked = Boolean(value);
    } else if (value !== undefined && value !== null) {
      element.value = String(value);
    }
  }

  function collect() {
    return fields().reduce((result, element, index) => {
      result[fieldKey(element, index)] = readValue(element);
      return result;
    }, {});
  }

  function setStatus(message) {
    if (statusNode) statusNode.textContent = message;
  }

  function save(showMessage = true) {
    const payload = {
      version: 1,
      savedAt: new Date().toISOString(),
      values: collect()
    };
    localStorage.setItem(storageKey, JSON.stringify(payload));
    if (showMessage) setStatus(`已保存在本机 · ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`);
    root.dataset.saved = "true";
  }

  function restore() {
    const raw = localStorage.getItem(storageKey);
    if (!raw) {
      setStatus("尚未保存，本页填写内容会自动保存在本机");
      return;
    }
    try {
      const payload = JSON.parse(raw);
      fields().forEach((element, index) => {
        const key = fieldKey(element, index);
        if (Object.prototype.hasOwnProperty.call(payload.values || {}, key)) {
          writeValue(element, payload.values[key]);
        }
      });
      const savedAt = payload.savedAt ? new Date(payload.savedAt).toLocaleString("zh-CN") : "未知时间";
      setStatus(`已恢复本机草稿 · ${savedAt}`);
    } catch (error) {
      console.error("无法恢复本机草稿", error);
      setStatus("本机草稿无法读取，请清空后重新填写");
    }
  }

  function reset() {
    const confirmed = window.confirm("只清空当前工具在本机保存的内容，确定继续吗？");
    if (!confirmed) return;
    localStorage.removeItem(storageKey);
    fields().forEach((element) => {
      if (element.type === "checkbox" || element.type === "radio") element.checked = false;
      else if (element.tagName === "SELECT") element.selectedIndex = 0;
      else element.value = "";
    });
    root.dataset.saved = "false";
    setStatus("当前工具已清空");
    document.dispatchEvent(new CustomEvent("brand-house-tool:reset"));
  }

  let saveTimer;
  function queueSave() {
    root.dataset.saved = "false";
    setStatus("正在保存本机草稿…");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => save(false), 250);
  }

  document.addEventListener("input", (event) => {
    if (event.target.matches("input, select, textarea")) queueSave();
  });
  document.addEventListener("change", (event) => {
    if (event.target.matches("input, select, textarea")) queueSave();
  });

  document.querySelectorAll('[data-action="save"]').forEach((button) => button.addEventListener("click", () => save(true)));
  document.querySelectorAll('[data-action="reset"]').forEach((button) => button.addEventListener("click", reset));
  document.querySelectorAll('[data-action="print"]').forEach((button) => button.addEventListener("click", () => window.print()));

  restore();
  window.BrandHouseTool = { collect, save, restore, reset, storageKey };
})();

