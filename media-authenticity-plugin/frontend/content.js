const RESULT_CARD_ID = "map-authenticity-result";
const ANALYZE_URL = "http://127.0.0.1:8000/analyze";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "VERIFY_TEXT") {
    return;
  }

  const text = (message.text || "").trim();
  if (!text) {
    sendResponse({ ok: false, error: "No text selected." });
    return;
  }

  analyzeAndShow(text)
    .then(() => sendResponse({ ok: true }))
    .catch((error) => {
      showResultCard({
        aiScore: null,
        patternData: null,
        tone: "error",
        claimStatus: error.message || "Analysis failed.",
        sources: [],
      });
      sendResponse({ ok: false, error: error.message });
    });

  return true;
});

async function analyzeAndShow(text) {
  showResultCard({
    aiScore: { label: "Analyzing..." },
    patternData: null,
    tone: "pending",
    claimStatus: "Checking AI probability and live source coverage.",
    sources: [],
  });

  const response = await fetch(ANALYZE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("Invalid response from analysis server.");
  }

  if (!response.ok) {
    const detail =
      typeof data?.detail === "string"
        ? data.detail
        : `Server error (${response.status}).`;
    throw new Error(detail);
  }

  if (!data?.ai_score || typeof data.claim_status !== "string") {
    throw new Error("Unexpected response format from analysis server.");
  }

  const isAi = Number(data.ai_score.percentage) >= 50;
  showResultCard({
    aiScore: data.ai_score,
    patternData: data.pattern_data,
    tone: isAi ? "ai" : "human",
    claimStatus: data.claim_status,
    sources: Array.isArray(data.sources) ? data.sources : [],
  });
}

function showResultCard({ aiScore, patternData, tone, claimStatus, sources }) {
  removeExistingCard();

  const card = document.createElement("div");
  card.id = RESULT_CARD_ID;
  card.className = `map-result-card map-tone-${tone}`;
  card.setAttribute("role", "status");
  card.setAttribute("aria-live", "polite");

  const header = document.createElement("div");
  header.className = "map-result-header";

  const title = document.createElement("div");
  title.className = "map-result-title";
  title.textContent = "Media Authenticity";

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "map-result-close";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.textContent = "✕";
  closeBtn.addEventListener("click", () => card.remove());

  header.append(title, closeBtn);

  const aiSection = document.createElement("section");
  aiSection.className = "map-result-section map-ai-section";
  const aiHeading = document.createElement("div");
  aiHeading.className = "map-section-heading";
  aiHeading.textContent = "AI Detection";
  const aiValue = document.createElement("strong");
  aiValue.className = "map-ai-value";
  aiValue.textContent = aiScore?.label || "Unavailable";
  aiSection.append(aiHeading, aiValue);

  const warningSection = document.createElement("section");
  warningSection.className = "map-warning-box";
  const warningBadge = document.createElement("strong");
  warningBadge.className = "map-warning-badge";
  warningBadge.textContent = "⚠️ Narrative Alert";
  const summary = document.createElement("p");
  summary.className = "map-summary-text";
  summary.textContent = patternData?.narrative_summary || "";
  warningSection.append(warningBadge, summary);

  const sourceSection = document.createElement("section");
  sourceSection.className = "map-result-section map-source-section";
  const sourceHeading = document.createElement("div");
  sourceHeading.className = "map-section-heading";
  sourceHeading.textContent = "Fact-Check / Source Verification";
  const claim = document.createElement("p");
  claim.className = "map-claim-status";
  claim.textContent = claimStatus || "No verification status available.";
  claim.dataset.tone = claimStatus?.startsWith("Verified") ? "verified" : "unverified";
  sourceSection.append(sourceHeading, claim);

  const links = document.createElement("ul");
  links.className = "map-source-list";
  (sources || []).slice(0, 3).forEach((source) => {
    if (!source?.title || !source?.url) return;
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = source.title;
    item.appendChild(link);
    links.appendChild(item);
  });
  if (links.children.length) sourceSection.appendChild(links);

  if (patternData?.pattern_detected === true && patternData.narrative_summary) {
    card.append(header, aiSection, warningSection, sourceSection);
  } else {
    card.append(header, aiSection, sourceSection);
  }
  document.documentElement.appendChild(card);
  positionNearSelection(card);
}

function positionNearSelection(card) {
  const selection = window.getSelection();
  if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    if (rect.width || rect.height) {
      const cardWidth = Math.min(360, window.innerWidth - 24);
      const left = Math.min(window.innerWidth - cardWidth - 12, Math.max(12, rect.left));
      const top = Math.min(window.innerHeight - 12, Math.max(12, rect.bottom + 10));
      card.style.top = `${top}px`;
      card.style.left = `${left}px`;
      card.style.right = "auto";
      return;
    }
  }

  card.style.top = "16px";
  card.style.right = "16px";
  card.style.left = "auto";
}

function removeExistingCard() {
  const existing = document.getElementById(RESULT_CARD_ID);
  if (existing) existing.remove();
}
