"use strict";
var obsidian = require("obsidian");

/**
 * Ensures Bases view type `kanban` is registered.
 * Base Board should register it; this retries after layout ready if load-order
 * left Home.base with "unknown view type: kanban".
 */
class SolarisKanbanFix extends obsidian.Plugin {
  async onload() {
    const hasKanban = () => {
      const bases = this.app.internalPlugins.getEnabledPluginById("bases");
      if (!bases || !bases.getRegistrations) return false;
      return Object.prototype.hasOwnProperty.call(bases.getRegistrations(), "kanban");
    };

    const baseBoardLoaded = () => !!this.app.plugins.plugins["base-board"];

    const tryStub = () => {
      if (hasKanban()) return true;
      const bases = this.app.internalPlugins.getEnabledPluginById("bases");
      if (!bases) return false;
      if (typeof obsidian.BasesView !== "function") {
        console.error("[solaris-kanban-fix] BasesView missing from API");
        return false;
      }

      class StubKanbanView extends obsidian.BasesView {
        constructor(controller, containerEl) {
          super(controller);
          this.containerEl = containerEl.createDiv("solaris-stub-kanban");
        }
        onload() {}
        onDataUpdated() {
          this.containerEl.empty();
          this.containerEl.createEl("p", {
            text:
              "Kanban stub — Base Board did not register view type `kanban`. " +
              "Enable Community plugin Base Board and Reload app.",
          });
          const data = this.data;
          if (!data) return;
          for (const g of data.groupedData || []) {
            const col = this.containerEl.createDiv();
            col.createEl("h4", {
              text: (g.key && g.key.toString && g.key.toString()) || "(No value)",
            });
            const ul = col.createEl("ul");
            for (const entry of g.entries || []) {
              ul.createEl("li", { text: entry.file.basename });
            }
          }
        }
      }

      try {
        const ok = this.registerBasesView("kanban", {
          name: "Kanban",
          icon: "lucide-kanban",
          factory: (controller, containerEl) =>
            new StubKanbanView(controller, containerEl),
        });
        console.info("[solaris-kanban-fix] stub register =>", ok);
        return !!ok;
      } catch (err) {
        console.error("[solaris-kanban-fix] stub register failed", err);
        return false;
      }
    };

    const attempt = (round) => {
      const bb = baseBoardLoaded();
      const kanban = hasKanban();
      console.info(
        `[solaris-kanban-fix] attempt ${round}: base-board=${bb} kanban=${kanban}`
      );
      if (kanban) return true;
      // Give Base Board another chance; only stub if still missing.
      return tryStub();
    };

    this.app.workspace.onLayoutReady(() => {
      const delays = [200, 800, 2000, 4000];
      delays.forEach((ms, i) => {
        window.setTimeout(() => {
          const ok = attempt(i + 1);
          if (ok && i === delays.length - 1 && !baseBoardLoaded()) {
            new obsidian.Notice(
              "Kanban view registered without Base Board — enable Base Board in Community plugins, then Reload.",
              10000
            );
          }
        }, ms);
      });
    });

    this.addCommand({
      id: "diagnose-kanban",
      name: "Solaris: Diagnose Bases kanban",
      callback: () => {
        const bases = this.app.internalPlugins.getEnabledPluginById("bases");
        const regs =
          bases && bases.getRegistrations ? Object.keys(bases.getRegistrations()) : [];
        const msg = [
          "bases enabled: " + !!bases,
          "base-board loaded: " + baseBoardLoaded(),
          "registered views: " + regs.join(", "),
          "has kanban: " + hasKanban(),
        ].join("\n");
        console.info("[solaris-kanban-fix]\n" + msg);
        new obsidian.Notice(msg, 12000);
        tryStub();
      },
    });
  }
}

module.exports = SolarisKanbanFix;
