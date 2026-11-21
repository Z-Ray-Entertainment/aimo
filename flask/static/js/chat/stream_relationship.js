import {
  appendUiNotice as renderUiNotice,
  setTurnRelationshipDebugNotice as renderTurnRelationshipDebugNotice,
} from "./message_renderer.js";

export function updateRelationshipUI(relationshipValue, tierName, relationshipImpact) {
  const relLabel = document.getElementById("rel-score-label");
  if (relLabel && tierName) {
    relLabel.textContent = tierName;
  }
  const galleryRelLabel = document.getElementById("gallery-rel-tier-label");
  if (galleryRelLabel && tierName) {
    galleryRelLabel.textContent = tierName;
  }
  const relWrap = document.querySelector(".relationship-bar-wrap[data-relationship-score]");
  if (!relWrap) return;

  relWrap.setAttribute("data-relationship-score", String(relationshipValue));
  if (tierName) {
    relWrap.setAttribute("title", tierName);
  }
  const pct = Math.max(0, Math.min(100, ((relationshipValue + 100) / 200) * 100));
  const fill = relWrap.querySelector(".relationship-fill");
  if (fill) fill.style.width = `${pct}%`;

  const heartIcon = relWrap.querySelector(".heart-icon");
  if (heartIcon) {
    const score = relationshipValue;
    if (score <= -60) {
      heartIcon.textContent = "💔";
      heartIcon.style.color = "#7A1C1C";
    } else if (score < 0) {
      heartIcon.textContent = "❤️‍🩹";
      heartIcon.style.color = "#A93226";
    } else if (score < 50) {
      heartIcon.textContent = "❤️";
      heartIcon.style.color = "#E74C3C";
    } else {
      heartIcon.textContent = "💖";
      heartIcon.style.color = "#FF69B4";
    }
  }

  const pulseClassMap = {
    positive: "relationship-pulse-positive",
    very_positive: "relationship-pulse-positive",
    negative: "relationship-pulse-negative",
    very_negative: "relationship-pulse-negative",
  };
  const pulseClass = pulseClassMap[relationshipImpact];
  if (pulseClass) {
    relWrap.classList.remove("relationship-pulse-positive", "relationship-pulse-negative");
    void relWrap.offsetWidth;
    relWrap.classList.add(pulseClass);
    relWrap.addEventListener(
      "animationend",
      () => relWrap.classList.remove(pulseClass),
      { once: true }
    );
  }
}

export function appendRelationshipDebugNotice(
  stream,
  relationshipValue,
  tierName,
  impact,
  delta,
  evaluatedTurns = null
) {
  if (!stream.getChatMetadata().isAdmin) return;
  if (typeof relationshipValue !== "number") return;
  const deltaText =
    typeof delta === "number" ? `${delta >= 0 ? "+" : ""}${delta}` : "?";
  const prefix =
    typeof evaluatedTurns === "number"
      ? `[Debug Relationship Recalc (${evaluatedTurns} turns)]`
      : "[Debug Relationship]";
  const impactLabel = impact || "neutral";
  const tierLabel = tierName || "";
  renderUiNotice(
    `${prefix} ${impactLabel} (${deltaText}) → ${relationshipValue} (${tierLabel})`
  );
}

export function setRelationshipDebug(enabled) {
  const messagesList = document.getElementById("chat-messages-list");
  const checkbox = document.getElementById("toggle-rel-debug-checkbox");
  if (messagesList) {
    messagesList.classList.toggle("show-rel-debug", Boolean(enabled));
  }
  if (checkbox) {
    checkbox.checked = Boolean(enabled);
  }
  try {
    localStorage.setItem("aimo_rel_debug", enabled ? "1" : "0");
  } catch (_) {}
}

export function initRelationshipDebugToggle(stream) {
  const meta = stream.getChatMetadata();
  if (!meta.isAdmin && !meta.canDebugRel) return;
  let enabled = false;
  try {
    enabled = localStorage.getItem("aimo_rel_debug") === "1";
  } catch (_) {}
  setRelationshipDebug(enabled);
}

export async function recalculateRelationship(stream, btn) {
  if (stream.isSending || stream.isGeneratingImage) return;
  const origHtml = window.setButtonLoading ? window.setButtonLoading(btn, "⏳") : btn?.innerHTML;
  if (btn) btn.disabled = true;

  try {
    const resp = await fetch(`/api/chat/${stream.sessionId}/recalculate-relationship`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: stream.getChatMetadata().sysLang }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const msg = data.error || window.t("Failed to recalculate relationship.");
      window.showToastError ? window.showToastError(msg, window.t("Error")) : alert(msg);
      return;
    }
    const meta = stream.getChatMetadata();
    if (Array.isArray(data.turn_results)) {
      data.turn_results.forEach((turn) => {
        renderTurnRelationshipDebugNotice(meta, turn.message_idx, turn.impact, turn.delta);
      });
    }
    if (typeof data.relationship_value === "number") {
      updateRelationshipUI(
        data.relationship_value,
        data.relationship_tier_name,
        data.relationship_impact
      );
      appendRelationshipDebugNotice(
        stream,
        data.relationship_value,
        data.relationship_tier_name,
        data.relationship_impact,
        data.relationship_delta,
        data.evaluated_turns
      );
    }
  } catch (err) {
    const msg = window.t("Connection error: {error}", { error: err.message });
    window.showToastError ? window.showToastError(msg, window.t("Error")) : alert(msg);
  } finally {
    if (window.resetButtonLoading && btn) {
      window.resetButtonLoading(btn, origHtml);
    } else if (btn) {
      btn.disabled = false;
    }
  }
}
