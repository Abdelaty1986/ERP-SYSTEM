document.addEventListener("DOMContentLoaded", function () {
  const moneyFormatter = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  document.querySelectorAll(".money").forEach(function (node) {
    const raw = (node.dataset.value || node.textContent || "").replace(/,/g, "").trim();
    if (!/^-?\d+(\.\d+)?$/.test(raw)) return;
    node.textContent = moneyFormatter.format(Number(raw));
  });

  const sidebar = document.getElementById("appSidebar");
  const mobileToggle = document.getElementById("mobileNavToggle");
  const collapseToggle = document.getElementById("sidebarCollapseToggle");
  const backdrop = document.getElementById("sidebarBackdrop");
  const media = window.matchMedia("(max-width: 992px)");

  const savedCollapsed = localStorage.getItem("ledgerxSidebarCollapsed");
  if (savedCollapsed === "1" && !media.matches) document.body.classList.add("sidebar-collapsed");

  function closeMobileSidebar() {
    if (!sidebar || !mobileToggle || !backdrop) return;
    sidebar.classList.remove("is-open");
    backdrop.hidden = true;
    mobileToggle.setAttribute("aria-expanded", "false");
    document.body.classList.remove("sidebar-open");
  }
  function openMobileSidebar() {
    if (!sidebar || !mobileToggle || !backdrop) return;
    sidebar.classList.add("is-open");
    backdrop.hidden = false;
    mobileToggle.setAttribute("aria-expanded", "true");
    document.body.classList.add("sidebar-open");
  }

  mobileToggle?.addEventListener("click", function () {
    sidebar?.classList.contains("is-open") ? closeMobileSidebar() : openMobileSidebar();
  });
  backdrop?.addEventListener("click", closeMobileSidebar);

  collapseToggle?.addEventListener("click", function () {
    if (media.matches) return;
    document.body.classList.toggle("sidebar-collapsed");
    localStorage.setItem("ledgerxSidebarCollapsed", document.body.classList.contains("sidebar-collapsed") ? "1" : "0");
  });

  document.querySelectorAll(".sidebar a").forEach(function (node) {
    node.addEventListener("click", function () { if (media.matches) closeMobileSidebar(); });
  });

  media.addEventListener("change", function (event) {
    closeMobileSidebar();
    if (event.matches) document.body.classList.remove("sidebar-collapsed");
    else if (localStorage.getItem("ledgerxSidebarCollapsed") === "1") document.body.classList.add("sidebar-collapsed");
  });
});
