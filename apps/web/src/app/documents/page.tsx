"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  FileText,
  Upload,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Languages,
  Eye,
  ArrowRight,
  Clock,
  Sparkles,
  Lock,
  RefreshCw,
  X,
  FileCheck2,
  Layers,
  Building2
} from "lucide-react";
import { useI18n } from "@/lib/i18n/context";
import {
  fetchDocuments,
  fetchDocumentDetail,
  uploadDocument,
  translateDocument,
  DocumentSummary,
  DocumentDetail
} from "@/lib/api-client";

export default function DocumentVaultPage() {
  const { language, t } = useI18n();
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<DocumentDetail | null>(null);
  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [targetLang, setTargetLang] = useState("en-US");

  useEffect(() => {
    loadDocumentList();
  }, []);

  async function loadDocumentList() {
    try {
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch (err) {
      console.error("Failed to load documents:", err);
    } finally {
      setLoading(false);
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const newDoc = await uploadDocument(file, "transcript");
      setSelectedDoc(newDoc);
      setCompareModalOpen(true);
      await loadDocumentList();
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setUploading(false);
    }
  };

  const handleViewComparison = async (docId: string) => {
    try {
      const detail = await fetchDocumentDetail(docId);
      setSelectedDoc(detail);
      setCompareModalOpen(true);
    } catch (err) {
      console.error("Failed to load doc detail:", err);
    }
  };

  const handleRetranslate = async () => {
    if (!selectedDoc) return;
    setTranslating(true);
    try {
      await translateDocument(selectedDoc.id, targetLang);
      const updated = await fetchDocumentDetail(selectedDoc.id);
      setSelectedDoc(updated);
    } catch (err) {
      console.error("Translation failed:", err);
    } finally {
      setTranslating(false);
    }
  };

  const getConfidenceBadge = (confidence?: string) => {
    switch (confidence) {
      case "high_confidence":
        return (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> High Confidence
          </span>
        );
      case "needs_review":
        return (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Needs Human Review
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
            Human Verification Required
          </span>
        );
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-600 dark:text-brand-400">
            <Lock className="w-4 h-4" /> Secure Academic Document Vault
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white mt-1">
            Document Vault & Translation Integrity
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Securely preserve original transcripts with SHA-256 integrity, automated entity extraction, and transparent machine translations.
          </p>
        </div>

        {/* Upload Button */}
        <div>
          <label className="px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold flex items-center gap-2 cursor-pointer shadow-sm transition-colors">
            <Upload className="w-4 h-4" />
            <span>{uploading ? "Uploading & Preserving..." : "Upload Academic Document"}</span>
            <input
              type="file"
              onChange={handleFileUpload}
              disabled={uploading}
              className="sr-only"
              accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.csv,.xlsx"
            />
          </label>
        </div>
      </div>

      {/* Mandatory Integrity Guarantee Card */}
      <div className="bg-gradient-to-r from-blue-900/10 via-indigo-900/10 to-brand-900/10 border border-blue-200 dark:border-blue-900/50 rounded-2xl p-6">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-brand-600 text-white flex items-center justify-center shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              Original Document Preservation Standard
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Your original uploaded files are <strong>never overwritten, altered, or deleted</strong> by machine extraction or translations. Every file is cryptographically hashed with SHA-256 for integrity verification. Machine translations are transparently marked as planning interpretations and are never represented as official certified university transcripts.
            </p>
          </div>
        </div>
      </div>

      {/* Document List Grid */}
      <div className="space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">
          Vaulted Academic Records ({documents.length})
        </h2>

        {documents.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-300 font-bold uppercase text-xs shrink-0">
                      {doc.file_type}
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800 flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" /> Preserved
                    </span>
                  </div>

                  <div className="mt-4">
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white truncate" title={doc.original_filename}>
                      {doc.original_filename}
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                      <span>{(doc.file_size_bytes / 1024).toFixed(1)} KB</span>
                      <span>&bull;</span>
                      <span>Lang: {doc.detected_language}</span>
                    </p>
                  </div>

                  {/* SHA-256 Checksum badge */}
                  <div className="mt-4 p-2 rounded-lg bg-slate-50 dark:bg-slate-850 border border-slate-100 dark:border-slate-800">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">SHA-256 Checksum</div>
                    <div className="text-[10px] font-mono text-slate-600 dark:text-slate-400 truncate mt-0.5">
                      {doc.file_sha256}
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-850 flex items-center justify-between">
                  <span className="text-[11px] text-slate-400">
                    Uploaded: {new Date(doc.uploaded_at).toLocaleDateString()}
                  </span>
                  <button
                    onClick={() => handleViewComparison(doc.id)}
                    className="text-xs font-semibold text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Compare Side-by-Side
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-12 text-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl">
            <FileText className="w-12 h-12 text-slate-300 dark:text-slate-700 mx-auto mb-3" />
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">No documents uploaded yet</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              Upload your high school transcripts, foreign diplomas (Haitian Baccalauréat, French Bac, IB), or community college grade reports to test automated extraction and translation integrity.
            </p>
          </div>
        )}
      </div>

      {/* Side-by-Side Comparison Modal */}
      {compareModalOpen && selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-slate-900 dark:text-white">
                    Document Intelligence & Side-by-Side Translation
                  </h3>
                  {getConfidenceBadge(selectedDoc.extraction?.extraction_confidence)}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  File: <span className="font-semibold text-slate-700 dark:text-slate-300">{selectedDoc.original_filename}</span> &bull; SHA-256: <span className="font-mono">{selectedDoc.file_sha256.substring(0, 16)}...</span>
                </p>
              </div>
              <button
                onClick={() => setCompareModalOpen(false)}
                className="p-2 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Translation Disclaimer Banner */}
            <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-900 text-xs text-amber-800 dark:text-amber-300 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  <strong>Non-Certified Machine Translation:</strong> This translation is generated for academic planning and admissions analysis. Official university matriculation may require a certified NACES/AACRAO credential evaluation.
                </span>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={targetLang}
                  onChange={(e) => setTargetLang(e.target.value)}
                  className="text-xs px-2 py-1 rounded border border-amber-300 bg-white dark:bg-slate-800 dark:border-amber-800"
                >
                  <option value="en-US">Translate to English</option>
                  <option value="fr-FR">Translate to Français</option>
                  <option value="ht-HT">Translate to Kreyòl</option>
                  <option value="es-419">Translate to Español</option>
                </select>
                <button
                  onClick={handleRetranslate}
                  disabled={translating}
                  className="px-2.5 py-1 rounded bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold flex items-center gap-1"
                >
                  <RefreshCw className={`w-3 h-3 ${translating ? "animate-spin" : ""}`} />
                  Translate
                </button>
              </div>
            </div>

            {/* Split Screen Container */}
            <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-200 dark:divide-slate-800 p-6 gap-6">
              {/* Left Column: Original Extracted Data */}
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-brand-600" />
                    Original Academic Record (Preserved)
                  </h4>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                    Source: {selectedDoc.detected_language}
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-850">
                    <div className="text-slate-400 text-[10px] uppercase font-semibold">Identified Institution</div>
                    <div className="font-bold text-slate-900 dark:text-white mt-0.5">
                      {selectedDoc.extraction?.detected_institution || "Academic Institution"}
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-850">
                    <div className="text-slate-400 text-[10px] uppercase font-semibold">Identified Qualification</div>
                    <div className="font-bold text-slate-900 dark:text-white mt-0.5">
                      {selectedDoc.extraction?.detected_qualification || "Secondary School Certificate"}
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-850">
                    <div className="text-slate-400 text-[10px] uppercase font-semibold">Grading Scale</div>
                    <div className="font-semibold text-slate-700 dark:text-slate-300 mt-0.5">
                      {selectedDoc.extraction?.detected_grading_scale || "Standard Scale"}
                    </div>
                  </div>
                </div>

                {/* Raw Extracted Text / Courses */}
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                    Extracted Text Representation
                  </div>
                  <pre className="p-3 rounded-xl bg-slate-900 text-slate-200 text-xs font-mono overflow-x-auto whitespace-pre-wrap max-h-48 leading-relaxed">
                    {selectedDoc.extraction?.extracted_text}
                  </pre>
                </div>
              </div>

              {/* Right Column: Translated Academic Record */}
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-brand-600 flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-brand-600" />
                    Translated Academic Record & Articulation
                  </h4>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-300">
                    Target: {selectedDoc.translations[0]?.target_language || "en-US"}
                  </span>
                </div>

                {selectedDoc.translations.length > 0 ? (
                  <div className="space-y-4 text-xs">
                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-700 whitespace-pre-line text-slate-800 dark:text-slate-200 leading-relaxed font-mono text-[11px]">
                      {selectedDoc.translations[0].translated_text}
                    </div>

                    {/* Translated Courses Table */}
                    {selectedDoc.translations[0].translated_data_json?.courses && (
                      <div className="space-y-2">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Translated Course Articulation Matrix
                        </div>
                        <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-100 dark:border-slate-800 rounded-xl overflow-hidden">
                          {selectedDoc.translations[0].translated_data_json.courses.map((c: any, idx: number) => (
                            <div key={idx} className="p-2.5 flex items-center justify-between bg-white dark:bg-slate-900 text-xs">
                              <div>
                                <span className="font-bold text-slate-900 dark:text-white">{c.code}</span>
                                <span className="text-slate-500 ms-2">{c.translated_title_en || c.title}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-emerald-600 dark:text-emerald-400">Grade: {c.grade}</span>
                                {c.us_equivalent && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
                                    US Equiv: {c.us_equivalent}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="text-[10px] text-slate-400 italic">
                      Engine: {selectedDoc.translations[0].translation_engine} &bull; Translated: {new Date(selectedDoc.translations[0].translated_at).toLocaleString()}
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center text-slate-500 text-xs">
                    No translation generated yet. Click &quot;Translate&quot; above to produce an academic translation.
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-200 dark:border-slate-800 flex justify-end">
              <button
                onClick={() => setCompareModalOpen(false)}
                className="px-5 py-2 rounded-xl bg-slate-900 dark:bg-white text-white dark:text-slate-900 text-xs font-semibold"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
