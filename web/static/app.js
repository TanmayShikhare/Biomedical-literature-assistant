(function () {
  const $ = (id) => document.getElementById(id);
  const q = $("q");
  const go = $("go");
  const status = $("status");
  const spinner = $("spinner");
  const disclaimer = $("disclaimer");
  const answerWrap = $("answer-wrap");
  const answerEl = $("answer");
  const copyBtn = $("copy-answer");
  const sourcesWrap = $("sources-wrap");
  const sourcesEl = $("sources");
  const examplesEl = $("examples");

  const EXAMPLES = [
    "How does tirzepatide compare to semaglutide for glycemic control in type 2 diabetes?",
    "What outcomes are commonly reported for semaglutide in type 2 diabetes trials?",
    "What do the retrieved abstracts say about GLP-1 agonists and body weight?",
  ];

  let lastAnswerMarkdown = "";

  EXAMPLES.forEach((text) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = text.length > 72 ? text.slice(0, 70) + "…" : text;
    b.title = text;
    b.addEventListener("click", () => {
      q.value = text;
      q.focus();
    });
    examplesEl.appendChild(b);
  });

  function setLoading(on) {
    go.disabled = on;
    spinner.classList.toggle("hidden", !on);
    status.textContent = on ? "Retrieving and synthesizing…" : "";
    status.classList.remove("err");
  }

  function showError(msg) {
    status.textContent = msg;
    status.classList.add("err");
  }

  /** Turn bare [PMID:n] into markdown links before parsing. */
  function pmidMarkdownLinks(text) {
    return (text || "").replace(
      /\[PMID:(\d+)\](?!\()/gi,
      (_, id) => `[PMID:${id}](https://pubmed.ncbi.nlm.nih.gov/${id}/)`
    );
  }

  function renderMarkdown(text) {
    lastAnswerMarkdown = text || "";
    const linked = pmidMarkdownLinks(lastAnswerMarkdown);
    if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
      answerEl.textContent = lastAnswerMarkdown;
      return;
    }
    const raw = marked.parse(linked, { mangle: false, headerIds: false });
    answerEl.innerHTML = DOMPurify.sanitize(raw);
    answerEl.querySelectorAll('a[href^="https://pubmed.ncbi.nlm.nih.gov/"]').forEach((a) => {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    });
  }

  function renderSources(passages) {
    sourcesEl.innerHTML = "";
    if (!passages || !passages.length) {
      sourcesWrap.classList.add("hidden");
      return;
    }
    passages.slice(0, 16).forEach((p) => {
      const li = document.createElement("li");
      const pmid = (p.pmid || "").toString().trim();
      const pubmed =
        pmid && /^\d+$/.test(pmid)
          ? `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`
          : "";
      const title = (p.title || "").trim();
      const snip = (p.snippet || "").trim().replace(/\s+/g, " ");
      const tkw = Array.isArray(p.topic_keywords) ? p.topic_keywords : [];
      const tid = p.topic_id != null ? String(p.topic_id) : "";
      const topicLine =
        tid !== "" && tkw.length
          ? '<span class="topic">Topic ' +
            escapeHtml(tid) +
            ": " +
            escapeHtml(tkw.join(", ")) +
            "</span>"
          : tid !== ""
            ? '<span class="topic">Topic ' + escapeHtml(tid) + "</span>"
            : "";
      const pmidHtml = pubmed
        ? '<span class="pmid"><a href="' +
          escapeHtml(pubmed) +
          '" target="_blank" rel="noopener noreferrer">PMID:' +
          escapeHtml(pmid) +
          "</a></span>"
        : '<span class="pmid">PMID:' + escapeHtml(pmid) + "</span>";
      li.innerHTML =
        pmidHtml +
        topicLine +
        (title ? '<span class="title">' + escapeHtml(title) + "</span>" : "") +
        (snip ? '<span class="snippet">' + escapeHtml(snip.slice(0, 280)) + (snip.length > 280 ? "…" : "") + "</span>" : "");
      sourcesEl.appendChild(li);
    });
    sourcesWrap.classList.remove("hidden");
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  copyBtn.addEventListener("click", async () => {
    if (!lastAnswerMarkdown) return;
    try {
      await navigator.clipboard.writeText(lastAnswerMarkdown);
      copyBtn.textContent = "Copied";
      copyBtn.classList.add("copied");
      setTimeout(() => {
        copyBtn.textContent = "Copy markdown";
        copyBtn.classList.remove("copied");
      }, 2000);
    } catch {
      copyBtn.textContent = "Copy failed";
      setTimeout(() => {
        copyBtn.textContent = "Copy markdown";
      }, 2000);
    }
  });

  async function run() {
    const question = (q.value || "").trim();
    if (!question) {
      showError("Enter a question.");
      return;
    }
    setLoading(true);
    copyBtn.disabled = true;
    answerWrap.classList.add("hidden");
    sourcesWrap.classList.add("hidden");
    disclaimer.classList.add("hidden");
    lastAnswerMarkdown = "";

    try {
      const res = await fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data.detail || res.statusText || "Request failed";
        showError(typeof detail === "string" ? detail : JSON.stringify(detail));
        setLoading(false);
        return;
      }
      disclaimer.textContent = data.disclaimer || "";
      disclaimer.classList.remove("hidden");
      renderMarkdown(data.answer || "");
      answerWrap.classList.remove("hidden");
      copyBtn.disabled = !lastAnswerMarkdown;
      renderSources(data.top_passages || []);
    } catch (e) {
      showError(e.message || "Network error — is the API running?");
    }
    setLoading(false);
  }

  go.addEventListener("click", run);
  q.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      run();
    }
  });
})();
