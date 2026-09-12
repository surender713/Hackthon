const RESULT_CARD_ID = "map-authenticity-result";
const ANALYZE_URL = "http://127.0.0.1:8000/analyze";
const ANALYZE_IMAGE_URL = "http://127.0.0.1:8000/analyze-image";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.action === "analyzeImage") {
    if (!message.srcUrl) {
      sendResponse({ ok: false, error: "No image URL provided." });
      return;
    }

    analyzeImageAndShow(message.srcUrl)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => {
        showImageResultCard({
          score: null,
          tone: "error",
          details: error.message || "Image analysis failed.",
        });
        sendResponse({ ok: false, error: error.message });
      });

    return true;
  }

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
        originalText: text,
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

async function analyzeImageAndShow(srcUrl) {
  showImageResultCard({
    score: { label: "Analyzing..." },
    tone: "pending",
    details: "Analyzing image authenticity...",
  });

  const imageResponse = await fetch(srcUrl);
  if (!imageResponse.ok) {
    throw new Error(`Unable to fetch image (${imageResponse.status}).`);
  }

  const imageData = await blobToDataUrl(await imageResponse.blob());
  const response = await fetch(ANALYZE_IMAGE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_data: imageData }),
  });

  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("Invalid response from image analysis server.");
  }

  if (!response.ok) {
    const detail =
      typeof data?.detail === "string"
        ? data.detail
        : `Image analysis server error (${response.status}).`;
    throw new Error(detail);
  }

  if (!data || typeof data.label !== "string") {
    throw new Error("Unexpected image analysis response.");
  }

  const isAi = Number(data.percentage) >= 50;
  showImageResultCard({
    score: data,
    tone: isAi ? "ai" : "human",
    details: data.manipulation_details || "No manipulation details provided.",
  });
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Unable to convert image data."));
    reader.readAsDataURL(blob);
  });
}

function showImageResultCard({ score, tone, details }) {
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
  title.textContent = "Image Authenticity";
  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "map-result-close";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.textContent = "✕";
  closeBtn.addEventListener("click", () => card.remove());
  header.append(title, closeBtn);

  const scoreSection = document.createElement("section");
  scoreSection.className = "map-result-section map-ai-section";
  const scoreHeading = document.createElement("div");
  scoreHeading.className = "map-section-heading";
  scoreHeading.textContent = "Image AI Detection";
  const scoreValue = document.createElement("strong");
  scoreValue.className = "map-ai-value";
  scoreValue.textContent = score?.label || "Unavailable";
  scoreSection.append(scoreHeading, scoreValue);

  const detailsSection = document.createElement("section");
  detailsSection.className = "map-result-section map-image-details";
  const detailsHeading = document.createElement("div");
  detailsHeading.className = "map-section-heading";
  detailsHeading.textContent = "Manipulation Details";
  const detailsText = document.createElement("p");
  detailsText.className = "map-summary-text";
  detailsText.textContent = details || "";
  detailsSection.append(detailsHeading, detailsText);

  card.append(header, scoreSection, detailsSection);
  document.documentElement.appendChild(card);
  positionNearSelection(card);
}

async function analyzeAndShow(text) {
  showResultCard({
    originalText: text,
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
    originalText: text,
    aiScore: data.ai_score,
    patternData: data.pattern_data,
    tone: isAi ? "ai" : "human",
    claimStatus: data.claim_status,
    sources: Array.isArray(data.sources) ? data.sources : [],
  });
}

function showResultCard({ originalText, aiScore, patternData, tone, claimStatus, sources }) {
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

  const verificationState = {
    original_text: originalText || "",
    ai_score: aiScore || null,
    pattern_data: patternData || null,
    claim_status: claimStatus || "",
    sources: Array.isArray(sources) ? sources : [],
  };

  const actionsFooter = document.createElement("footer");
  actionsFooter.className = "map-actions-footer";

  const exportJsonButton = createExportButton("⬇️ Export JSON", () => {
    const report = createReport(verificationState);
    downloadReport(
      JSON.stringify(report, null, 2),
      `authenticity-report-${getFilenameTimestamp(report.timestamp)}.json`,
      "application/json",
    );
  });
  const exportHtmlButton = createExportButton("⬇️ Export HTML", () => {
    const report = createReport(verificationState);
    downloadReport(
      createHtmlReport(report),
      `authenticity-report-${getFilenameTimestamp(report.timestamp)}.html`,
      "text/html",
    );
  });
  const exportTxtButton = createExportButton("⬇️ Export TXT", () => {
    const report = createReport(verificationState);
    downloadReport(
      createTextReport(report),
      `authenticity-report-${getFilenameTimestamp(report.timestamp)}.txt`,
      "text/plain",
    );
  });

  actionsFooter.append(exportJsonButton, exportHtmlButton, exportTxtButton);
  card.appendChild(actionsFooter);
  document.documentElement.appendChild(card);
  positionNearSelection(card);
}

function createReport(verificationState) {
  return {
    ...verificationState,
    timestamp: new Date().toISOString(),
  };
}

function createExportButton(label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "map-export-btn";
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function getFilenameTimestamp(timestamp) {
  return timestamp.replace(/[:.]/g, "-");
}

function downloadReport(content, filename, mimeType) {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.hidden = true;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function createHtmlReport(report) {
  const patternData = report.pattern_data || {};
  const patternDetected = patternData.pattern_detected === true;
  const sources = report.sources
    .map(
      (source) =>
        `<li><a href="${escapeHtml(source?.url || "")}">${escapeHtml(
          source?.title || source?.url || "Source",
        )}</a></li>`,
    )
    .join("");

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Media Authenticity Report</title>
  <style>
    :root { color-scheme: light; font-family: Arial, sans-serif; }
    body { max-width: 760px; margin: 40px auto; padding: 0 24px; color: #1f2937; line-height: 1.6; }
    h1 { color: #0f172a; font-size: 28px; }
    h2 { margin-top: 28px; color: #334155; font-size: 18px; }
    .meta { color: #64748b; font-size: 14px; }
    .original-text { white-space: pre-wrap; padding: 16px; border-left: 4px solid #94a3b8; background: #f8fafc; }
    .result { padding: 14px 16px; border: 1px solid #cbd5e1; border-radius: 8px; background: #fff; }
    .warning { border-left: 4px solid #f59e0b; background: #fffbeb; }
    .label { font-weight: 700; }
    a { color: #1d4ed8; }
  </style>
</head>
<body>
  <h1>Media Authenticity Report</h1>
  <p class="meta">Generated: ${escapeHtml(report.timestamp)}</p>
  <h2>Original Text</h2>
  <div class="original-text">${escapeHtml(report.original_text)}</div>
  <h2>AI Detection</h2>
  <div class="result"><span class="label">${escapeHtml(
    report.ai_score?.label || "Unavailable",
  )}</span></div>
  <h2>Narrative Pattern Detection</h2>
  <div class="result${patternDetected ? " warning" : ""}">
    <span class="label">${patternDetected ? "Narrative Alert" : "No recurring pattern detected"}</span>
    <p>${escapeHtml(patternData.narrative_summary || "")}</p>
  </div>
  <h2>Fact-Check / Source Verification</h2>
  <div class="result">${escapeHtml(report.claim_status || "No verification status available.")}</div>
  ${sources ? `<ul>${sources}</ul>` : ""}
</body>
</html>`;
}

function createTextReport(report) {
  const patternData = report.pattern_data || {};
  const sources = report.sources
    .map((source) => `- ${source?.title || source?.url || "Source"}: ${source?.url || ""}`)
    .join("\n");

  return `MEDIA AUTHENTICITY REPORT
===========================
Generated: ${report.timestamp}

ORIGINAL TEXT
-------------
${report.original_text}

AI DETECTION
------------
${report.ai_score?.label || "Unavailable"}

NARRATIVE PATTERN DETECTION
---------------------------
Detected: ${patternData.pattern_detected === true ? "Yes" : "No"}
${patternData.narrative_summary || "No recurring misinformation patterns detected."}

FACT-CHECK / SOURCE VERIFICATION
--------------------------------
${report.claim_status || "No verification status available."}
${sources ? `\nSOURCES\n-------\n${sources}` : ""}
`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
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
