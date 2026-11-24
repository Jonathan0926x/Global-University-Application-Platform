"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Bot,
  Send,
  Sparkles,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Globe2,
  RefreshCw,
  BookOpen,
  GraduationCap,
  Layers,
  ArrowRight
} from "lucide-react";
import { useI18n } from "@/lib/i18n/context";
import {
  askCounselor,
  fetchCounselorHistory,
  fetchInstitutionDetail,
  CounselorMessage,
  Citation
} from "@/lib/api-client";

export default function CounselorPage() {
  const { language, direction, t } = useI18n();
  const [messages, setMessages] = useState<CounselorMessage[]>([]);
  const [inputQuery, setInputQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState<string>(language.tag);
  const [contextInstId, setContextInstId] = useState<string | undefined>(undefined);
  const [contextInstName, setContextInstName] = useState<string | undefined>(undefined);
  const [contextPathway, setContextPathway] = useState<string | undefined>(undefined);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSelectedLanguage(language.tag);
  }, [language.tag]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const instId = params.get("institution_id") || undefined;
    const pathway = params.get("pathway") || undefined;
    setContextInstId(instId);
    setContextPathway(pathway);
    if (instId) {
      fetchInstitutionDetail(instId)
        .then((d) => setContextInstName(d.official_name))
        .catch(() => {});
    }
  }, []);

  useEffect(() => {
    // Initial welcome message from the counselor
    const welcomeText =
      language.tag === "ht-HT"
        ? "Bonjou! Mwen se Konseye Admisyon Entènasyonal AI UniGlobe la. Mwen ka ede w konprann kijan pou w transfere soti nan yon Community College pou ale nan yon inivèsite 4-an, kòman pou w evalye Baccalauréat Ayisyen w la, oswa egzijans admisyon premye ane. Kijan mwen ka ede w jodi a?"
        : language.tag === "es-419"
        ? "¡Hola! Soy tu Consejero de Admisiones Internacionales IA de UniGlobe. Puedo ayudarte con transferencias universitarias, convalidación de títulos internacionales y requisitos de admisión. ¿En qué puedo orientarte hoy?"
        : language.tag === "fr-FR"
        ? "Bonjour ! Je suis votre Conseiller d'Admission Internationale IA UniGlobe. Je peux vous guider pour vos transferts universitaires, l'évaluation de vos diplômes étrangers (Baccalauréat, etc.) et vos candidatures globales. Comment puis-je vous aider ?"
        : "Hello! I am your UniGlobe Multilingual AI Admissions Counselor. I provide verified guidance on US community college transfer articulation (UC/CSU, Assist.org), international credential recognition (Baccalauréat, IB, CBSE), and global university admissions. What questions can I answer for you today?";

    setMessages([
      {
        id: "welcome-1",
        conversation_id: "conv-1",
        role: "assistant",
        content: welcomeText,
        language: language.tag,
        citations: [
          {
            title: "ASSIST Official Statewide Student Transfer Information System",
            url: "https://assist.org",
            institution: "California Community Colleges & UC/CSU",
            verified_at: "2026-11-15",
            summary: "Official course-to-course articulation agreements for California higher education.",
          },
          {
            title: "University of California Transfer Pathways",
            url: "https://admission.universityofcalifornia.edu/admission-requirements/transfer-requirements/",
            institution: "University of California System",
            verified_at: "2026-11-20",
            summary: "Minimum 60 semester units, 7-course pattern, and campus GPA standards.",
          },
        ],
        disclaimer: "AI Admissions Interpretation — Not an official university admissions decision.",
        created_at: new Date().toISOString(),
      },
    ]);
  }, [language.tag]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSendMessage = async (e?: React.FormEvent, customPrompt?: string) => {
    if (e) e.preventDefault();
    const query = customPrompt || inputQuery;
    if (!query.trim() || loading) return;

    const userMsg: CounselorMessage = {
      id: `user-${Date.now()}`,
      conversation_id: "conv-1",
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
      const response = await askCounselor(query, selectedLanguage, undefined, contextInstId, contextPathway);
      setMessages((prev) => [...prev, response]);
    } catch (err) {
      console.error("Counselor query failed:", err);
      // Fallback message
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          conversation_id: "conv-1",
          role: "assistant",
          content:
            "I apologize, but I am momentarily disconnected from the admissions knowledge graph. Please verify that your local backend service is running on port 8000.",
          language: selectedLanguage,
          citations: [],
          disclaimer: "AI Counselor Service Offline Fallback",
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const samplePrompts = [
    {
      label: "Kreyòl: Transfè Docs",
      text: "Ki dokiman mwen bezwen pou m aplike kòm etidyan transfè nan UC Berkeley?",
    },
    {
      label: "Haitian Student CC Transfer",
      text:
        selectedLanguage === "ht-HT"
          ? "Kijan mwen ka transfere soti nan yon community college pou ale nan UC Berkeley si mwen gen yon Baccalauréat Ayisyen?"
          : "How can a student from Haiti transfer from a US Community College to UC Berkeley with a Haitian Baccalauréat?",
    },
    {
      label: "Oxford / UK UCAS Intl",
      text: "What are the international qualifications, English test deadlines, and UCAS dates for University of Oxford?",
    },
  ];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Top Banner */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 flex items-center justify-center text-white shadow-md">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                  Multilingual AI Admissions Counselor
                </h1>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800">
                  Grounded & Verified
                </span>
                {contextInstName && (
                  <span className="text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                    Context: {contextInstName}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Multi-country credential recognition, transfer articulation, and verified university source citations.
              </p>
            </div>
          </div>

          {/* Language selector chips for conversation */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-slate-400 font-medium me-1">Chat Language:</span>
            {[
              { code: "ht-HT", name: "Kreyòl Ayisyen", flag: "🇭🇹" },
              { code: "en-US", name: "English", flag: "🇺🇸" },
              { code: "fr-FR", name: "Français", flag: "🇫🇷" },
              { code: "es-419", name: "Español", flag: "🇲🇽" },
              { code: "ar-SA", name: "العربية", flag: "🇸🇦" },
            ].map((l) => (
              <button
                key={l.code}
                onClick={() => setSelectedLanguage(l.code)}
                className={`text-xs px-2.5 py-1 rounded-lg border font-medium flex items-center gap-1.5 transition-all ${
                  selectedLanguage === l.code
                    ? "bg-brand-600 text-white border-brand-600 shadow-xs"
                    : "bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-slate-300"
                }`}
              >
                <span>{l.flag}</span>
                <span>{l.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Ethical Non-Binding Disclaimer Notice */}
        <div className="mt-4 p-3 rounded-xl bg-amber-50/70 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 text-[11px] text-amber-900 dark:text-amber-300 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <span>
            <strong>Transparency Notice:</strong> UniGlobe AI provides admissions interpretations and articulation guidance grounded in published university policies. These explanations do not constitute official admissions decisions or certified university equivalency guarantees. Always confirm final matriculation criteria with the respective institution.
          </span>
        </div>
      </div>

      {/* Main Chat Interface */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm flex flex-col h-[650px] overflow-hidden">
        {/* Messages Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id}
                className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
              >
                {/* Avatar */}
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 text-white text-xs font-bold ${
                    isUser
                      ? "bg-brand-600"
                      : "bg-slate-900 dark:bg-slate-700"
                  }`}
                >
                  {isUser ? "You" : <Bot className="w-4 h-4" />}
                </div>

                {/* Message Bubble */}
                <div
                  className={`max-w-2xl rounded-2xl p-4 text-sm leading-relaxed ${
                    isUser
                      ? "bg-brand-600 text-white"
                      : "bg-slate-50 dark:bg-slate-800/80 text-slate-900 dark:text-slate-100 border border-slate-100 dark:border-slate-800"
                  }`}
                >
                  <div className="whitespace-pre-line">{msg.content}</div>

                  {/* Citations block (Assistant messages only) */}
                  {!isUser && msg.citations && msg.citations.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-200/60 dark:border-slate-700/60 space-y-2">
                      <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        Verified Official Source Citations ({msg.citations.length})
                      </div>
                      <div className="grid grid-cols-1 gap-2">
                        {msg.citations.map((cite, idx) => (
                          <a
                            key={idx}
                            href={cite.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-2.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 hover:border-brand-500 dark:hover:border-brand-400 transition-colors flex items-start justify-between gap-3 group"
                          >
                            <div className="space-y-0.5">
                              <div className="text-xs font-semibold text-slate-900 dark:text-white group-hover:text-brand-600 dark:group-hover:text-brand-400 flex items-center gap-1">
                                {cite.title}
                                <ExternalLink className="w-3 h-3 text-slate-400" />
                              </div>
                              <p className="text-[11px] text-slate-500">
                                {cite.institution} &bull; Verified: {cite.verified_at}
                              </p>
                              {cite.summary && (
                                <p className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 italic">
                                  &ldquo;{cite.summary}&rdquo;
                                </p>
                              )}
                            </div>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Timestamp & Disclaimer */}
                  {!isUser && msg.disclaimer && (
                    <div className="mt-2 text-[10px] text-slate-400 dark:text-slate-500 italic">
                      {msg.disclaimer}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="flex gap-3">
              <div className="w-9 h-9 rounded-xl bg-slate-900 text-white flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 animate-spin" />
              </div>
              <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800 text-slate-500 text-sm flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-brand-600" />
                <span>Consulting verified transfer articulation matrix and international credential guide...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Prompt Suggestions */}
        <div className="px-6 py-2 bg-slate-50 dark:bg-slate-850/60 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2 overflow-x-auto text-xs">
          <span className="text-slate-400 shrink-0 font-medium">Quick Prompts:</span>
          {samplePrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(undefined, p.text)}
              className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:border-brand-500 text-slate-700 dark:text-slate-300 shrink-0 text-left transition-colors"
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Input Form */}
        <form
          onSubmit={(e) => handleSendMessage(e)}
          className="p-4 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex items-center gap-3"
        >
          <input
            type="text"
            placeholder={
              selectedLanguage === "ht-HT"
                ? "Poze yon kesyon sou admisyon, transfè, oswa ekivalans diplòm an Kreyòl..."
                : "Ask any question about transfer pathways, requirements, or foreign credentials..."
            }
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            className="flex-1 px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <button
            type="submit"
            disabled={!inputQuery.trim() || loading}
            className="px-5 py-3 rounded-xl bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white font-semibold text-sm flex items-center gap-2 transition-all shadow-sm shrink-0"
          >
            <span>Send</span>
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
