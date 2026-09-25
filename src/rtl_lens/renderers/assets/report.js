(() => {
  "use strict";

  const setupFindingFilters = () => {
    const severity = document.querySelector("#severity-filter");
    const baseline = document.querySelector("#baseline-filter");
    const engine = document.querySelector("#engine-filter");
    const count = document.querySelector("[data-testid='visible-count']");
    const rows = Array.from(document.querySelectorAll("[data-testid='finding-row']"));

    if (!(severity instanceof HTMLSelectElement) ||
        !(baseline instanceof HTMLSelectElement) ||
        !(engine instanceof HTMLSelectElement) ||
        !(count instanceof HTMLElement)) {
      return;
    }

    const applyFilters = () => {
      let visible = 0;
      for (const row of rows) {
        if (!(row instanceof HTMLElement)) continue;
        let engines = [];
        try {
          engines = JSON.parse(row.dataset.engines || "[]");
        } catch (_error) {
          engines = [];
        }
        const matchesSeverity = severity.value === "all" || row.dataset.severity === severity.value;
        const matchesBaseline = baseline.value === "all" || row.dataset.baseline === baseline.value;
        const matchesEngine = engine.selectedIndex === 0 || engines.includes(engine.value);
        row.hidden = !(matchesSeverity && matchesBaseline && matchesEngine);
        if (!row.hidden) visible += 1;
      }
      count.textContent = `${visible} ${visible === 1 ? "finding" : "findings"} visible`;
    };

    severity.addEventListener("change", applyFilters);
    baseline.addEventListener("change", applyFilters);
    engine.addEventListener("change", applyFilters);
    applyFilters();
  };

  const setupRelationshipSearch = () => {
    const search = document.querySelector("#relationship-search");
    const count = document.querySelector("[data-testid='relationship-visible-count']");
    const rows = Array.from(document.querySelectorAll("[data-testid='relationship-row']"));

    if (!(search instanceof HTMLInputElement) || !(count instanceof HTMLElement)) return;

    const foldForSearch = (value) => value.normalize("NFKC").toLowerCase();

    const applySearch = () => {
      const query = foldForSearch(search.value);
      let visible = 0;
      for (const row of rows) {
        if (!(row instanceof HTMLElement)) continue;
        const matches = foldForSearch(row.dataset.search || "").includes(query);
        row.hidden = !matches;
        if (matches) visible += 1;
      }
      count.textContent = `${visible} ${visible === 1 ? "relationship" : "relationships"} visible`;
    };

    search.addEventListener("input", applySearch);
    applySearch();
  };

  setupFindingFilters();
  setupRelationshipSearch();
})();
