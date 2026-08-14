/* Copyright (c) 2026 Guido Esser
 * Licensed under the Elastic License 2.0 — see LICENSE file for details.
 * Community Edition — self-hosting free. SaaS/Managed Service requires commercial license. */
/* ============================================================
   Prozesswerk — App Logic
   ============================================================ */

// ---- State ----
const state = {
  currentBpmnXml: '',
  currentNotes: null,
  currentProcessDef: null,
  isRecording: false,
  recognition: null,
  isGenerating: false,
};

// ---- DOM Refs ----
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
  textarea: $('#process-input'),
  generateBtn: $('#generate-btn'),
  micBtn: $('#mic-btn'),
  errorDisplay: $('#error-display'),
  errorMessage: $('#error-message'),
  errorClose: $('#error-close'),
  configStatus: $('#config-status'),
  configDot: $('#config-dot'),
  configLabel: $('#config-label'),
  configInfo: $('#config-info'),
  configExample: $('#config-example'),
  exampleSelect: $('#example-select'),
  results: $('#results-section'),
  iterationSection: $('#iteration-section'),
  iterationInput: $('#iteration-input'),
  iterationBtn: $('#iteration-btn'),
  xmlContent: $('#xml-content'),
  notesContent: $('#notes-content'),
  structureContent: $('#structure-content'),
  xmlTab: $('#tab-xml'),
  notesTab: $('#tab-notes'),
  structureTab: $('#tab-structure'),
  downloadBtn: $('#download-btn'),
  editorBtn: $('#editor-btn'),
  copyXmlBtn: $('#copy-xml-btn'),
};

// ---- API Helpers ----
const API_BASE = '/api';

async function apiPost(endpoint, body) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

async function apiGet(endpoint) {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// ---- Configuration Check ----
async function checkConfig() {
  dom.configDot.className = 'status-dot checking';
  dom.configLabel.textContent = 'Checking configuration…';

  try {
    const config = await apiGet('/config');
    if (config.llm_configured) {
      dom.configDot.className = 'status-dot connected';
      dom.configLabel.textContent = 'LLM verbunden';
      dom.configInfo.textContent = `${config.llm_model || 'Model'} · ${config.llm_base_url || ''}`;
      dom.configExample.style.display = '';
    } else {
      dom.configDot.className = 'status-dot';
      dom.configLabel.textContent = 'LLM nicht konfiguriert';
      dom.configInfo.textContent = '';
    }
  } catch (err) {
    dom.configDot.className = 'status-dot';
    dom.configLabel.textContent = 'Verbindungsfehler';
    dom.configInfo.textContent = err.message;
  }
}

// ---- Generate BPMN ----
async function generateBPMN(text) {
  if (state.isGenerating) return;
  state.isGenerating = true;
  dom.generateBtn.classList.add('loading');
  dom.generateBtn.disabled = true;
  hideError();

  try {
    const data = await apiPost('/generate', { text });

    if (!data.success) {
      throw new Error('Generation fehlgeschlagen');
    }

    // Update state
    state.currentBpmnXml = data.bpmn_xml || '';
    state.currentNotes = data.notes || null;
    state.currentProcessDef = data.process_definition || null;

    showResults(data);
  } catch (err) {
    showError(err.message);
  } finally {
    state.isGenerating = false;
    dom.generateBtn.classList.remove('loading');
    dom.generateBtn.disabled = false;
  }
}

// ---- Iteration (Refinement) ----
async function iterateBPMN() {
  const text = dom.iterationInput.value.trim();
  if (!text || state.isGenerating) return;

  dom.iterationBtn.classList.add('loading');
  dom.iterationBtn.disabled = true;
  hideError();

  try {
    // Send refinement with existing definition as context (IDs preserved)
    const body = { text };
    if (state.currentProcessDef) {
      body.existing_definition = state.currentProcessDef;
    }
    const data = await apiPost('/generate', body);

    if (!data.success) {
      throw new Error('Verfeinerung fehlgeschlagen');
    }

    state.currentBpmnXml = data.bpmn_xml || '';
    state.currentNotes = data.notes || null;
    state.currentProcessDef = data.process_definition || null;

    dom.iterationInput.value = '';
    showResults(data);
  } catch (err) {
    showError(err.message);
  } finally {
    dom.iterationBtn.classList.remove('loading');
    dom.iterationBtn.disabled = false;
  }
}

// ---- Show Results ----
function showResults(data) {
  // Store text for tabs
  const xml = data.bpmn_xml || state.currentBpmnXml || '';
  const notes = data.notes || state.currentNotes || '';
  const processDef = data.process_definition || state.currentProcessDef || '';

  // Populate tabs
  dom.xmlContent.textContent = xml;
  dom.notesContent.innerHTML = formatNotes(notes);
  dom.structureContent.textContent = typeof processDef === 'object'
    ? JSON.stringify(processDef, null, 2)
    : String(processDef || '');

  // Show results section
  dom.results.classList.add('visible');
  dom.results.style.display = 'block';

  // Show iteration section
  dom.iterationSection.style.display = 'block';

  // Activate first tab (XML)
  switchTab('xml');

  // Enable download
  dom.downloadBtn.disabled = false;

  // Enable editor button
  dom.editorBtn.disabled = false;

  // Scroll to results
  dom.results.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function formatNotes(notes) {
  if (!notes) return '<em>Keine Notizen verfügbar.</em>';
  if (typeof notes === 'object' && !Array.isArray(notes)) {
    const parts = [];
    if (notes.assumptions && notes.assumptions.length) {
      parts.push('<h4>Annahmen</h4><ul>' + notes.assumptions.map(a => `<li>${escapeHtml(a)}</li>`).join('') + '</ul>');
    }
    if (notes.open_questions && notes.open_questions.length) {
      parts.push('<h4>Offene Fragen</h4><ul>' + notes.open_questions.map(q => `<li>${escapeHtml(q)}</li>`).join('') + '</ul>');
    }
    if (notes.improvements && notes.improvements.length) {
      parts.push('<h4>Verbesserungsvorschläge</h4><ul>' + notes.improvements.map(i => `<li>${escapeHtml(i)}</li>`).join('') + '</ul>');
    }
    return parts.length ? parts.join('') : '<em>Keine Notizen</em>';
  }
  return String(notes)
    .split('\n')
    .filter((l) => l.trim())
    .map((l) => `<p>${escapeHtml(l)}</p>`)
    .join('');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ---- Tab Switching ----
function switchTab(tab) {
  dom.xmlTab.classList.toggle('active', tab === 'xml');
  dom.notesTab.classList.toggle('active', tab === 'notes');
  dom.structureTab.classList.toggle('active', tab === 'structure');

  document.querySelectorAll('.tab-content').forEach((el) => el.classList.remove('active'));
  const contentMap = {
    xml: $('#tab-content-xml'),
    notes: $('#tab-content-notes'),
    structure: $('#tab-content-structure'),
  };
  if (contentMap[tab]) contentMap[tab].classList.add('active');

  dom.copyXmlBtn.style.display = tab === 'xml' ? 'inline-flex' : 'none';
}

// ---- Download BPMN ----
function downloadBPMN() {
  const xml = dom.xmlContent.textContent;
  if (!xml) return;

  const blob = new Blob([xml], { type: 'application/xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'process.bpmn';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---- Copy to Clipboard ----
function copyXml() {
  const xml = dom.xmlContent.textContent;
  if (!xml) return;

  navigator.clipboard.writeText(xml).then(() => {
    dom.copyXmlBtn.classList.add('copy-success');
    dom.copyXmlBtn.innerHTML = '✓ Kopiert';
    setTimeout(() => {
      dom.copyXmlBtn.classList.remove('copy-success');
      dom.copyXmlBtn.innerHTML = '📋 Kopieren';
    }, 2000);
  }).catch(() => {
    const textarea = document.createElement('textarea');
    textarea.value = xml;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
  });
}

// ---- Speech Recognition ----
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    dom.micBtn.style.display = 'none';
    return;
  }

  state.recognition = new SpeechRecognition();
  state.recognition.lang = 'de-DE';
  state.recognition.continuous = false;
  state.recognition.interimResults = false;

  state.recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    dom.textarea.value += (dom.textarea.value ? ' ' : '') + transcript;
    stopRecording();
  };

  state.recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error);
    stopRecording();
    if (event.error === 'not-allowed') {
      showError('Mikrofonzugriff verweigert. Bitte erlaube den Zugriff in den Browser-Einstellungen.');
    }
  };

  state.recognition.onend = () => {
    if (state.isRecording) stopRecording();
  };
}

function toggleRecording() {
  if (state.isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

function startRecording() {
  if (!state.recognition) return;
  try {
    state.recognition.start();
    state.isRecording = true;
    dom.micBtn.classList.add('recording');
    dom.micBtn.title = 'Aufnahme beenden';
  } catch (err) {
    console.error('Failed to start recording:', err);
  }
}

function stopRecording() {
  if (state.recognition) {
    try { state.recognition.stop(); } catch (_) {}
  }
  state.isRecording = false;
  dom.micBtn.classList.remove('recording');
  dom.micBtn.title = 'Spracheingabe';
}

// ---- Error Handling ----
function showError(message) {
  dom.errorMessage.textContent = message;
  dom.errorDisplay.classList.add('visible');
  dom.errorDisplay.style.display = 'flex';
}

function hideError() {
  dom.errorDisplay.classList.remove('visible');
  dom.errorDisplay.style.display = 'none';
}

// ---- Event Listeners ----
function initEventListeners() {
  // Generate button
  dom.generateBtn.addEventListener('click', () => {
    const text = dom.textarea.value.trim();
    if (text) generateBPMN(text);
  });

  // Enter key in textarea (Ctrl+Enter or Cmd+Enter)
  dom.textarea.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      const text = dom.textarea.value.trim();
      if (text) generateBPMN(text);
    }
  });

  // Mic button
  dom.micBtn.addEventListener('click', toggleRecording);

  // Example dropdown
  const examples = {
    versicherung: 'Ein Kunde meldet einen Schadensfall bei seiner Versicherung. Der Sachbearbeiter prüft die Police und erstellt eine erste Einschätzung. Ist der Schaden über 1000€, wird der Fall an einen externen Gutachter weitergeleitet. Der Gutachter erstellt ein Gutachten und schickt es zurück. Danach erfolgt die Auszahlung an den Kunden. Liegt der Schaden unter 1000€, wird direkt ausgezahlt.',
    urlaub: 'Ein Mitarbeiter stellt einen Urlaubsantrag. Der direkte Vorgesetzte prüft den Antrag. Wenn der Urlaub mit der Urlaubsplanung vereinbar ist, genehmigt er ihn und die Personalabteilung trägt ihn ein. Andernfalls lehnt er ab und der Mitarbeiter erhält eine Absage mit Begründung. Bei Unvollständigkeit geht der Antrag zur Nachbesserung zurück.',
    bestellung: 'Ein Kunde gibt eine Bestellung über den Webshop auf. Das System prüft die Verfügbarkeit der Artikel im Lager. Wenn alle Artikel verfügbar sind, wird die Bestellung an den Versand weitergeleitet und der Kunde erhält eine Versandbestätigung. Falls ein Artikel nicht verfügbar ist, wird der Kunde per E-Mail benachrichtigt und gefragt, ob er auf den Artikel warten oder die Bestellung teilen möchte.',
    rechnung: 'Die Buchhaltung erhält eine Rechnung per E-Mail. Ein Sachbearbeiter prüft die Rechnung auf formale Richtigkeit und gibt sie im System ein. Wenn der Rechnungsbetrag unter 500€ liegt, wird die Rechnung automatisch zur Zahlung freigegeben. Bei höheren Beträgen muss ein Vorgesetzter die Rechnung zusätzlich genehmigen. Wird die Genehmigung verweigert, geht die Rechnung mit einer Notiz zurück an den Sachbearbeiter.',
    onboarding: 'Die Personalabteilung legt einen neuen Mitarbeiter im System an. Die IT richtet automatisch Zugänge zu E-Mail, VPN und Fachanwendungen ein. Gleichzeitig bestellt die Verwaltung die Büroausstattung. Sobald beide Teilprozesse abgeschlossen sind, erstellt die Personalabteilung einen Willkommensbrief und vereinbart einen Onboarding-Termin mit dem Mitarbeiter.',
  };

  dom.exampleSelect.addEventListener('change', () => {
    const key = dom.exampleSelect.value;
    if (key && examples[key]) {
      dom.textarea.value = examples[key];
      dom.textarea.focus();
    }
  });

  // Error close
  dom.errorClose.addEventListener('click', hideError);

  // Tab buttons
  dom.xmlTab.addEventListener('click', () => switchTab('xml'));
  dom.notesTab.addEventListener('click', () => switchTab('notes'));
  dom.structureTab.addEventListener('click', () => switchTab('structure'));

  // Download
  dom.downloadBtn.addEventListener('click', downloadBPMN);

  // Copy XML
  dom.copyXmlBtn.addEventListener('click', copyXml);

  // Open in Editor
  dom.editorBtn.addEventListener('click', () => {
    const xml = dom.xmlContent.textContent;
    if (!xml) return;
    localStorage.setItem('bpmn-editor-xml', xml);
    if (state.currentProcessDef) {
      localStorage.setItem('bpmn-editor-process-def', JSON.stringify(state.currentProcessDef));
    }
    if (state.currentNotes) {
      localStorage.setItem('bpmn-editor-notes', JSON.stringify(state.currentNotes));
    }
    window.open('/modeler.html', '_self');
  });

  // Iteration
  dom.iterationBtn.addEventListener('click', iterateBPMN);
  dom.iterationInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      iterateBPMN();
    }
  });
}

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  initSpeechRecognition();
  checkConfig();

  // Auto-load text from Process Interview page
  const interviewText = localStorage.getItem('bpmn-interview-text');
  if (interviewText) {
    localStorage.removeItem('bpmn-interview-text');
    dom.textarea.value = interviewText;
    dom.textarea.focus();
  }

  // Restore from editor (user clicked "Zurück" after editing)
  const returnXml = localStorage.getItem('bpmn-editor-return-xml');
  if (returnXml) {
    localStorage.removeItem('bpmn-editor-return-xml');
    state.currentBpmnXml = returnXml;

    const storedDef = localStorage.getItem('bpmn-editor-process-def');
    if (storedDef) {
      try { state.currentProcessDef = JSON.parse(storedDef); } catch (_) {}
    }

    const storedNotes = localStorage.getItem('bpmn-editor-notes');
    if (storedNotes) {
      try { state.currentNotes = JSON.parse(storedNotes); } catch (_) {}
    }

    showResults({
      bpmn_xml: returnXml,
      notes: state.currentNotes,
      process_definition: state.currentProcessDef,
    });

    // Pre-focus iteration input for convenience
    setTimeout(() => dom.iterationInput.focus(), 100);
  }
});
