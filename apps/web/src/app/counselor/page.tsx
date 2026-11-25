"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Bot,
  Send,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  MessageSquarePlus,
  History,
  Trash2,
  Search,
  Database,
  ArrowUpRight,
  HelpCircle,
  Sparkles,
  BookOpen,
} from "lucide-react";
import { useI18n } from "@/lib/i18n/context";
import {
  askCounselor,
  fetchCounselorHistory,
  deleteCounselorConversation,
  fetchInstitutionDetail,
  searchInstitutions,
  type CounselorConversation,
  type CounselorMessage,
  type InstitutionV3,
} from "@/lib/api-client";

const WELCOME_MESSAGES: Record<string, string> = {
  "ht-HT":
    "Bonjou! Mwen se Konseye Admisyon AI UniGlobe ki konekte ak baz done PostgreSQL & pgvector nou an. Mwen ka eksplike egzijans admisyon verifye, dat limit, frè inivèsite, bous, akò transfè ASSIST.org, ak fason Baccalauréat Ayisyen ou an (0–20) evalye sou Pwofil Inivèsèl ou. Kijan m ka ede w?",
  "es-419":
    "¡Hola! Soy tu Consejero de Admisiones IA de UniGlobe conectado a nuestra base pgvector en PostgreSQL. Puedo consultar requisitos verificados, fechas límite, costos reales, becas, equivalencias de transferencia y el contexto de tu Perfil Universal. ¿En qué puedo ayudarte hoy?",
  "fr-FR":
    "Bonjour ! Je suis le Conseiller IA d'UniGlobe connecté à notre base PostgreSQL & pgvector. Je peux analyser les exigences d'admission vérifiées, les dates limites, les coûts, les bourses, les accords de transfert et votre Profil Universel. Comment puis-je vous aider ?",
  "ar-SA":
    "مرحبًا! أنا مستشار القبول الجامعي الذكي في UniGlobe، المتصل مباشرة بقاعدة بيانات PostgreSQL و pgvector. يمكنني مساعدتك في المتطلبات الموثقة والمواعيد النهائية والرسوم والمنح الدراسية ومعادلة الساعات المعتمدة وملفك الشخصي. كيف أساعدك اليوم؟",
  "en-US":
    "Hello! I am your UniGlobe Multilingual AI Admissions Counselor grounded via hybrid pgvector + PostgreSQL search. Ask me about verified admission requirements, deadlines, tuition & net price, official scholarships, Transfer Tier 1/2/3 articulation, international credentials (Baccalauréat, Abitur, A-Levels), or your saved Universal Profile & Match scores.",
};

function getWelcomeMessage(tag: string): CounselorMessage {
  const prefix = tag.split("-")[0].toLowerCase();
  const matchedKey =
    Object.keys(WELCOME_MESSAGES).find((k) => k === tag) ||
    Object.keys(WELCOME_MESSAGES).find((k) => k.toLowerCase().startsWith(prefix)) ||
    "en-US";

  return {
    id: `welcome-${matchedKey}`,
    conversation_id: "",
    role: "assistant",
    content: WELCOME_MESSAGES[matchedKey],
    language: tag,
    citations: [
      {
        title: "ASSIST Official Statewide Student Transfer Information System",
        url: "https://assist.org",
        institution: "California Community Colleges & UC/CSU",
        verified_at: "2026-11-24",
        summary: "Official course-to-course articulation agreements for California higher education.",
        source_type: "articulation_agreement",
        epistemic_tier: "official",
      },
      {
        title: "University of California Transfer Pathways",
        url: "https://admission.universityofcalifornia.edu/admission-requirements/transfer-requirements/",
        institution: "University of California System",
        verified_at: "2026-11-24",
        summary: "Minimum 60 semester units, 7-course pattern, and campus GPA standards.",
        source_type: "official_institutional",
        epistemic_tier: "official",
      },
    ],
    epistemic_breakdown: {
      suggested_workflows: [
        { label: "4D Match Engine", href: "/matching", workflow_type: "matching" },
        { label: "Transfer Credit Matrix", href: "/transfer", workflow_type: "transfer" },
        { label: "Document Vault", href: "/documents", workflow_type: "documents" },
      ],
    },
    disclaimer:
      "AI Interpretation — Grounded in UniGlobe PostgreSQL records via pgvector; not an official university admissions decision.",
    created_at: new Date().toISOString(),
  };
}

function tierBadgeStyle(tier?: string) {
  switch (tier) {
    case "historical":
      return { label: "Historical Pattern", cls: "bg-sky-50 text-sky-800 border-sky-200" };
    case "ai_interpretation":
      return { label: "AI Interpretation", cls: "bg-amber-50 text-amber-800 border-amber-200" };
    case "student_vault":
      return { label: "Student Vault", cls: "bg-zinc-100 text-zinc-800 border-zinc-300" };
    default:
      return { label: "Official Verified", cls: "bg-emerald-50 text-emerald-800 border-emerald-200" };
  }
}

export default function CounselorPage() {
  const { language, direction, t } = useI18n();

  const [messages, setMessages] = useState<CounselorMessage[]>([]);
  const [threads, setThreads] = useState<CounselorConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | undefined>(undefined);
  const [inputQuery, setInputQuery] = useState("");
  const [loading, setLoading] = useState(false);

  const [selectedLanguage, setSelectedLanguage] = useState<string>(language.tag);
  const [contextInstId, setContextInstId] = useState<string | undefined>(undefined);
  const [contextInstName, setContextInstName] = useState<string | undefined>(undefined);
  const [contextPathway, setContextPathway] = useState<string | undefined>(undefined);

  // Target university quick selector
  const [instSearchQuery, setInstSearchQuery] = useState("");
  const [instSearchResults, setInstSearchResults] = useState<InstitutionV3[]>([]);
  const [showThreadsMobile, setShowThreadsMobile] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSelectedLanguage(language.tag);
  }, [language.tag]);

  // Load URL parameters + conversation threads from backend
  useEffect(() => {
    let active = true;
    (async () => {
      if (typeof window !== "undefined") {
        const params = new URLSearchParams(window.location.search);
        const instId = params.get("institution_id") || undefined;
        const pathway = params.get("pathway") || undefined;
        setContextInstId(instId);
        setContextPathway(pathway);
        if (instId) {
          fetchInstitutionDetail(instId)
            .then((d) => {
              if (active) setContextInstName(d.official_name);
            })
            .catch(() => {});
        }
      }

      const history = await fetchCounselorHistory().catch(() => []);
      if (!active) return;
      setThreads(history);
      setMessages([getWelcomeMessage(language.tag)]);
    })();
    return () => {
      active = false;
    };
  }, [language.tag]);

  // Scroll to newest message when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Debounced institution picker search
  useEffect(() => {
    const q = instSearchQuery.trim();
    if (q.length < 2) {
      setInstSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await searchInstitutions({ q, limit: 5 });
        setInstSearchResults(res.items || []);
      } catch {
        setInstSearchResults([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [instSearchQuery]);

  const handleStartNewChat = () => {
    setActiveConversationId(undefined);
    setContextInstId(undefined);
    setContextInstName(undefined);
    setMessages([getWelcomeMessage(selectedLanguage)]);
  };

  const handleSelectThread = (conv: CounselorConversation) => {
    setActiveConversationId(conv.id);
    setContextInstId(conv.active_institution_id || undefined);
    setContextPathway(conv.active_applicant_type || undefined);
    if (conv.active_institution_id) {
      fetchInstitutionDetail(conv.active_institution_id)
        .then((d) => setContextInstName(d.official_name))
        .catch(() => {});
    } else {
      setContextInstName(undefined);
    }
    setMessages(conv.messages?.length ? conv.messages : [getWelcomeMessage(conv.primary_language)]);
    setShowThreadsMobile(false);
  };

  const handleDeleteThread = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const ok = await deleteCounselorConversation(convId);
    if (ok) {
      setThreads((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        handleStartNewChat();
      }
    }
  };

  const handleSendMessage = async (e?: React.FormEvent, customPrompt?: string) => {
    if (e) e.preventDefault();
    const query = customPrompt || inputQuery;
    if (!query.trim() || loading) return;

    const userMsg: CounselorMessage = {
      id: `user-${Date.now()}`,
      conversation_id: activeConversationId || "pending",
      role: "user",
      content: query,
      language: selectedLanguage,
      citations: [],
      disclaimer: "",
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery("");
    setLoading(true);

    try {
      const response = await askCounselor(
        query,
        selectedLanguage,
        activeConversationId,
        contextInstId,
        contextPathway
      );
      setActiveConversationId(response.conversation_id);
      setMessages((prev) => [...prev, response]);

      // Update tracked context badge if backend resolved an institution
      if (response.epistemic_breakdown?.context_institution_id) {
        setContextInstId(response.epistemic_breakdown.context_institution_id);
        if (response.epistemic_breakdown.context_institution_name) {
          setContextInstName(response.epistemic_breakdown.context_institution_name);
        }
      }
      if (response.epistemic_breakdown?.context_applicant_type) {
        setContextPathway(response.epistemic_breakdown.context_applicant_type);
      }

      // Refresh thread sidebar
      fetchCounselorHistory()
        .then((hist) => setThreads(hist))
        .catch(() => {});
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          conversation_id: activeConversationId || "offline",
          role: "assistant",
          content:
            "Unable to reach the PostgreSQL pgvector RAG Counselor API. Verify the backend server is running on port 8000.",
          language: selectedLanguage,
          citations: [],
          disclaimer: "AI Counselor Connection Fallback",
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const samplePrompts = [
    {
      label: "Kreyòl: UC Berkeley Transfè",
      text: "Ki dokiman ak kredi mwen bezwen pou m transfere soti nan Community College pou UC Berkeley ak yon Baccalauréat Ayisyen?",
    },
    {
      label: "English: Follow-up Tuition & Aid",
      text: "What are UC Berkeley tuition costs, deadlines, and international scholarships?",
    },
    {
      label: "العربية: المنح والتكاليف في MIT",
      text: "ما هي متطلبات القبول والمنح الدراسية للطلاب الدوليين في MIT؟",
    },
    {
      label: "Français: TUM Munich",
      text: "Quelles sont les exigences et les frais pour Technical University of Munich ?",
    },
    {
      label: "Missing / Uncurated Check",
      text: "What are the verified transfer scholarships and admission requirements for Harvard University?",
    },
  ];

  return (
    <div dir={direction} className="min-h-screen bg-[#fafafc] text-zinc-900 pb-16">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-6 space-y-5">
        {/* Top Header Card */}
        <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs space-y-4">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-zinc-900 text-white">
                <Bot className="h-5 w-5" />
              </div>
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900">
                    {t("counselor.title", "RAG Multilingual AI Admissions Counselor")}
                  </h1>
                  <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800">
                    <Database className="h-3 w-3" />
                    pgvector + PostgreSQL FTS
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-zinc-600 max-w-3xl">
                  {t(
                    "counselor.subtitle",
                    "Retrieval-grounded in UniGlobe PostgreSQL & pgvector across verified requirements, deadlines, costs, scholarships, transfer agreements, and your Universal Profile."
                  )}
                </p>
              </div>
            </div>

            {/* Language Selector Pills */}
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { code: "en-US", name: "English", flag: "🇺🇸" },
                { code: "ht-HT", name: "Kreyòl", flag: "🇭🇹" },
                { code: "fr-FR", name: "Français", flag: "🇫🇷" },
                { code: "es-419", name: "Español", flag: "🇲🇽" },
                { code: "ar-SA", name: "العربية", flag: "🇸🇦" },
              ].map((l) => (
                <button
                  key={l.code}
                  type="button"
                  onClick={() => setSelectedLanguage(l.code)}
                  className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors ${
                    selectedLanguage === l.code
                      ? "border-zinc-900 bg-zinc-900 text-white"
                      : "border-zinc-200 bg-zinc-50 text-zinc-700 hover:bg-zinc-100"
                  }`}
                >
                  <span>{l.flag}</span>
                  <span>{l.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Active Context + Pathway Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-100 pt-3 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-zinc-700">Context:</span>
              {contextInstName ? (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 font-medium text-indigo-800">
                  {contextInstName}
                  <button
                    type="button"
                    onClick={() => {
                      setContextInstId(undefined);
                      setContextInstName(undefined);
                    }}
                    className="ms-1 text-indigo-600 hover:text-indigo-900 font-bold"
                    aria-label="Clear university context"
                  >
                    ×
                  </button>
                </span>
              ) : (
                <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-zinc-600">
                  Global Knowledge Base (Any University)
                </span>
              )}

              <select
                value={contextPathway || "transfer"}
                onChange={(e) => setContextPathway(e.target.value)}
                aria-label="Applicant pathway context"
                className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1 text-xs font-medium text-zinc-800"
              >
                <option value="transfer">Transfer Pathway</option>
                <option value="first_year">First-Year Pathway</option>
              </select>

              <div className="relative">
                <div className="flex items-center gap-1 rounded-lg border border-zinc-300 bg-white px-2.5 py-1">
                  <Search className="h-3.5 w-3.5 text-zinc-500" />
                  <input
                    type="text"
                    value={instSearchQuery}
                    onChange={(e) => setInstSearchQuery(e.target.value)}
                    placeholder="Lock university context..."
                    className="w-40 sm:w-52 bg-transparent text-xs text-zinc-900 focus:outline-none"
                  />
                </div>
                {instSearchResults.length > 0 && (
                  <ul className="absolute z-30 mt-1 w-72 rounded-xl border border-zinc-200 bg-white shadow-lg divide-y divide-zinc-100 overflow-hidden">
                    {instSearchResults.map((inst) => (
                      <li key={inst.id}>
                        <button
                          type="button"
                          onClick={() => {
                            setContextInstId(inst.id);
                            setContextInstName(inst.official_name);
                            setInstSearchQuery("");
                            setInstSearchResults([]);
                          }}
                          className="w-full px-3 py-2 text-start text-xs hover:bg-zinc-50"
                        >
                          <div className="font-semibold text-zinc-900">{inst.official_name}</div>
                          <div className="text-[11px] text-zinc-500">
                            {[inst.city, inst.state_province, inst.country_code].filter(Boolean).join(", ")}
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowThreadsMobile((v) => !v)}
                className="lg:hidden inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700"
              >
                <History className="h-3.5 w-3.5" />
                Threads ({threads.length})
              </button>
              <button
                type="button"
                onClick={handleStartNewChat}
                className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-800 hover:bg-zinc-50"
              >
                <MessageSquarePlus className="h-3.5 w-3.5" />
                {t("counselor.new_chat", "New Conversation")}
              </button>
            </div>
          </div>

          <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50/70 px-3.5 py-2.5 text-[11px] text-amber-900">
            <AlertTriangle className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
            <span>
              <strong>Provenance & Guardrail Policy:</strong> Official verified records, historical patterns, and personalized AI interpretations are kept separate. Unverified requirements, passed deadlines, cross-source conflicts, and missing scholarships are flagged explicitly rather than guessed.
            </span>
          </div>
        </section>

        {/* Main Workspace: Threads Sidebar + Conversation Stream */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Threads Sidebar */}
          <aside
            className={`lg:col-span-3 rounded-2xl border border-zinc-200 bg-white p-4 shadow-xs flex flex-col gap-3 ${
              showThreadsMobile ? "block" : "hidden lg:flex"
            } max-h-[700px] overflow-y-auto`}
          >
            <div className="flex items-center justify-between border-b border-zinc-100 pb-2.5">
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-zinc-700">
                <History className="h-3.5 w-3.5" />
                Conversation Memory
              </span>
              <span className="text-[11px] text-zinc-500">{threads.length}</span>
            </div>

            {threads.length === 0 ? (
              <p className="text-xs text-zinc-500 py-4">
                Your follow-up threads persist here automatically so context is never lost.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {threads.map((conv) => (
                  <li key={conv.id}>
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => handleSelectThread(conv)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") handleSelectThread(conv);
                      }}
                      className={`group flex items-start justify-between gap-2 rounded-xl border p-2.5 text-xs cursor-pointer transition-colors ${
                        activeConversationId === conv.id
                          ? "border-indigo-300 bg-indigo-50/70 text-indigo-950"
                          : "border-zinc-200/80 bg-zinc-50/60 text-zinc-800 hover:bg-zinc-100"
                      }`}
                    >
                      <div className="min-w-0">
                        <p className="font-semibold truncate">{conv.title}</p>
                        <p className="text-[10px] text-zinc-500 mt-0.5">
                          {conv.primary_language} • {conv.active_applicant_type || "general"}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => handleDeleteThread(conv.id, e)}
                        aria-label="Delete conversation"
                        className="opacity-70 hover:opacity-100 text-zinc-500 hover:text-rose-700 p-1 shrink-0"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </aside>

          {/* Chat Panel */}
          <div className="lg:col-span-9 rounded-2xl border border-zinc-200 bg-white shadow-xs flex flex-col h-[700px] overflow-hidden">
            <div className="flex-1 overflow-y-auto p-5 space-y-5">
              {messages.map((msg) => {
                const isUser = msg.role === "user";
                const eb = msg.epistemic_breakdown || undefined;
                const msgRtl = msg.language?.startsWith("ar");

                return (
                  <div
                    key={msg.id}
                    className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
                  >
                    <div
                      className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 text-xs font-bold ${
                        isUser ? "bg-indigo-700 text-white" : "bg-zinc-900 text-white"
                      }`}
                    >
                      {isUser ? "You" : <Bot className="h-4 w-4" />}
                    </div>

                    <div
                      dir={msgRtl ? "rtl" : "ltr"}
                      className={`max-w-3xl rounded-2xl p-4 text-sm leading-relaxed space-y-3 ${
                        isUser
                          ? "bg-indigo-700 text-white"
                          : "bg-zinc-50 border border-zinc-200 text-zinc-900"
                      }`}
                    >
                      <div className="whitespace-pre-line">{msg.content}</div>

                      {/* Epistemic Context / Missing Warning Chips */}
                      {!isUser && eb && (
                        <div className="space-y-2.5 pt-2 border-t border-zinc-200/80 text-xs">
                          {eb.retrieval_stats && typeof eb.retrieval_stats.returned === "number" && (
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-zinc-600">
                              <span className="inline-flex items-center gap-1 rounded-full border border-zinc-200 bg-white px-2 py-0.5 font-medium">
                                <Sparkles className="h-3 w-3 text-indigo-600" />
                                Retrieved {eb.retrieval_stats.returned} chunk(s) via pgvector + FTS
                              </span>
                              {eb.context_institution_name && (
                                <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 font-medium text-indigo-800">
                                  Active Institution: {eb.context_institution_name}
                                </span>
                              )}
                            </div>
                          )}

                          {eb.missing_or_conflicting && eb.missing_or_conflicting.length > 0 && (
                            <div className="rounded-xl border border-amber-200 bg-amber-50 p-2.5 text-[11px] text-amber-900">
                              <div className="flex items-center gap-1.5 font-semibold mb-1">
                                <HelpCircle className="h-3.5 w-3.5 text-amber-700" />
                                Data Gaps & Conflict Alerts ({eb.missing_or_conflicting.length})
                              </div>
                              <ul className="list-disc ps-4 space-y-0.5">
                                {eb.missing_or_conflicting.slice(0, 4).map((w, idx) => (
                                  <li key={idx}>{w}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {eb.suggested_workflows && eb.suggested_workflows.length > 0 && (
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-[11px] font-semibold text-zinc-600">
                                Connected Workflows:
                              </span>
                              {eb.suggested_workflows.map((wf, idx) => (
                                <Link
                                  key={idx}
                                  href={wf.href}
                                  className="inline-flex items-center gap-1 rounded-lg border border-zinc-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-zinc-800 hover:bg-zinc-100 transition-colors"
                                >
                                  {wf.label}
                                  <ArrowUpRight className="h-3 w-3 text-indigo-700" />
                                </Link>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Verified Citations Block */}
                      {!isUser && msg.citations && msg.citations.length > 0 && (
                        <div className="pt-3 border-t border-zinc-200 space-y-2">
                          <div className="text-[11px] font-bold uppercase tracking-wider text-zinc-600 flex items-center gap-1.5">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700" />
                            Source Citations ({msg.citations.length})
                          </div>
                          <div className="grid grid-cols-1 gap-2">
                            {msg.citations.map((cite, idx) => {
                              const tb = tierBadgeStyle(cite.epistemic_tier);
                              return (
                                <a
                                  key={idx}
                                  href={cite.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="rounded-xl border border-zinc-200 bg-white p-2.5 hover:border-indigo-400 transition-colors block"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <span className="text-xs font-semibold text-zinc-900 inline-flex items-center gap-1">
                                      {cite.title}
                                      <ExternalLink className="h-3 w-3 text-zinc-500" />
                                    </span>
                                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${tb.cls}`}>
                                      {tb.label}
                                    </span>
                                  </div>
                                  <p className="text-[11px] text-zinc-600 mt-0.5">
                                    {cite.institution} • Source: {cite.source_type || "official"} • Verified: {cite.verified_at}
                                  </p>
                                  {cite.summary && (
                                    <p className="text-[11px] text-zinc-600 mt-1 line-clamp-2">
                                      {cite.summary}
                                    </p>
                                  )}
                                </a>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {!isUser && msg.disclaimer && (
                        <div className="text-[10px] text-zinc-500 italic pt-1">
                          {msg.disclaimer}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {loading && (
                <div className="flex gap-3">
                  <div className="h-9 w-9 rounded-xl bg-zinc-900 text-white flex items-center justify-center shrink-0">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  </div>
                  <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-4 text-xs text-zinc-600 flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-indigo-700" />
                    <span>Querying PostgreSQL pgvector index, FTS, and Universal Profile context...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Quick Multilingual Prompts */}
            <div className="border-t border-zinc-200 bg-zinc-50 px-4 py-2 flex items-center gap-2 overflow-x-auto text-xs">
              <span className="font-semibold text-zinc-500 shrink-0">Prompts:</span>
              {samplePrompts.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSendMessage(undefined, p.text)}
                  className="shrink-0 rounded-lg border border-zinc-200 bg-white px-2.5 py-1 text-zinc-700 hover:border-indigo-400 hover:text-indigo-800 transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Message Input */}
            <form
              onSubmit={(e) => handleSendMessage(e)}
              className="border-t border-zinc-200 bg-white p-3.5 flex items-center gap-2.5"
            >
              <input
                type="text"
                placeholder={
                  selectedLanguage === "ht-HT"
                    ? "Poze yon kesyon an Kreyòl (ekzanp: dat limit, frè, transfè)..."
                    : selectedLanguage === "ar-SA"
                    ? "اطرح سؤالك بالعربية حول القبول أو المنح أو الرسوم أو معادلة الساعات..."
                    : selectedLanguage === "fr-FR"
                    ? "Posez votre question en français (exigences, bourses, coûts, transfert)..."
                    : selectedLanguage === "es-419"
                    ? "Haz una pregunta en español sobre requisitos, costos, becas o transferencia..."
                    : "Ask about requirements, deadlines, costs, scholarships, transfer credits, or follow up..."
                }
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                className="flex-1 rounded-xl border border-zinc-300 bg-zinc-50 px-3.5 py-2.5 text-sm text-zinc-900 focus:border-indigo-500 focus:bg-white focus:outline-none"
              />
              <button
                type="submit"
                disabled={!inputQuery.trim() || loading}
                className="inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-4 py-2.5 text-xs font-semibold text-white hover:bg-zinc-800 disabled:opacity-50 transition-colors shrink-0"
              >
                <span>{t("counselor.send", "Send")}</span>
                <Send className="h-3.5 w-3.5" />
              </button>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
}
