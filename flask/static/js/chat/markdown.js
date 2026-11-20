export function escapeHtml(raw) {
  return String(raw || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function renderInlineMarkdown(escaped) {
  const codePlaceholders = [];
  let text = escaped.replace(/`([^`\n]+)`/g, (_, code) => {
    const idx = codePlaceholders.length;
    codePlaceholders.push(`<code>${code}</code>`);
    return `\x00CODE${idx}\x00`;
  });

  text = text.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/__(.+?)__/g, "<strong>$1</strong>");
  text = text.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  text = text.replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");
  text = text.replace(/~~(.+?)~~/g, "<del>$1</del>");

  text = text.replace(/\x00CODE(\d+)\x00/g, (_, idx) => codePlaceholders[Number(idx)] || "");
  return text;
}

export function renderChatMarkdown(rawText) {
  if (!rawText) return "";
  const normalized = String(rawText).replace(/\r\n/g, "\n");

  const fencedBlocks = [];
  const withPlaceholders = normalized.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = fencedBlocks.length;
    fencedBlocks.push(
      `<pre class="md-code-block"><code data-lang="${escapeHtml(lang)}">${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`
    );
    return `\n\x00FENCED${idx}\x00\n`;
  });

  const lines = withPlaceholders.split("\n");
  const htmlParts = [];
  let inUl = false;
  let inOl = false;

  const closeLists = () => {
    if (inUl) {
      htmlParts.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      htmlParts.push("</ol>");
      inOl = false;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    const fencedMatch = trimmed.match(/^\x00FENCED(\d+)\x00$/);
    if (fencedMatch) {
      closeLists();
      htmlParts.push(fencedBlocks[Number(fencedMatch[1])] || "");
      continue;
    }

    if (!trimmed) {
      closeLists();
      continue;
    }

    const headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      closeLists();
      const level = headingMatch[1].length + 1;
      htmlParts.push(`<h${level} class="md-heading">${renderInlineMarkdown(escapeHtml(headingMatch[2]))}</h${level}>`);
      continue;
    }

    const quoteMatch = line.match(/^>\s?(.*)$/);
    if (quoteMatch) {
      closeLists();
      htmlParts.push(`<blockquote class="md-quote">${renderInlineMarkdown(escapeHtml(quoteMatch[1]))}</blockquote>`);
      continue;
    }

    const ulMatch = line.match(/^\s*[-*]\s+(.+)$/);
    if (ulMatch) {
      if (inOl) {
        htmlParts.push("</ol>");
        inOl = false;
      }
      if (!inUl) {
        htmlParts.push('<ul class="md-list">');
        inUl = true;
      }
      htmlParts.push(`<li>${renderInlineMarkdown(escapeHtml(ulMatch[1]))}</li>`);
      continue;
    }

    const olMatch = line.match(/^\s*\d+\.\s+(.+)$/);
    if (olMatch) {
      if (inUl) {
        htmlParts.push("</ul>");
        inUl = false;
      }
      if (!inOl) {
        htmlParts.push('<ol class="md-list">');
        inOl = true;
      }
      htmlParts.push(`<li>${renderInlineMarkdown(escapeHtml(olMatch[1]))}</li>`);
      continue;
    }

    closeLists();
    htmlParts.push(`<p class="md-p">${renderInlineMarkdown(escapeHtml(line))}</p>`);
  }

  closeLists();
  return htmlParts.join("");
}
