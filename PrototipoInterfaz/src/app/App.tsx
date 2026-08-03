import { useState, useRef, useEffect } from "react";
import {
  Zap, LayoutDashboard, Dumbbell, ClipboardList, BarChart3, Bot,
  Flame, TrendingUp, Play, CheckCircle2, Circle, Plus, Send,
  Sparkles, Target, Clock, ArrowUp, Activity, Lock, RefreshCw,
  Check, X, Eye, EyeOff, ChevronRight, ChevronDown, ChevronUp,
  Trophy, Star, ArrowLeft, Timer, SkipForward, User, Settings,
  Bell, Search, Filter, Layers, Calendar,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar,
} from "recharts";

// ─── Constants & types ───────────────────────────────────────────────────────

const DISPLAY: React.CSSProperties = { fontFamily: "'Barlow Condensed', sans-serif" };
const MONO: React.CSSProperties    = { fontFamily: "'JetBrains Mono', monospace" };

type Tab = "home" | "routines" | "exercises" | "stats" | "coach";
type Screen =
  | "splash" | "login" | "register"
  | "home" | "routines" | "exercises" | "stats" | "coach"
  | "session-active" | "session-summary"
  | "rank" | "exercise-detail" | "routine-detail";

// ─── Data ────────────────────────────────────────────────────────────────────

const WEEKLY_VOL = [
  { w: "S1", v: 12400 }, { w: "S2", v: 14200 }, { w: "S3", v: 13800 },
  { w: "S4", v: 16500 }, { w: "S5", v: 15900 }, { w: "S6", v: 18200 },
  { w: "S7", v: 17600 }, { w: "S8", v: 21300 },
];

const MUSCLE_DATA = [
  { g: "Pecho", s: 24 }, { g: "Espalda", s: 28 }, { g: "Piernas", s: 32 },
  { g: "Hombros", s: 16 }, { g: "Brazos", s: 18 },
];

const EXERCISES = [
  { id: 1, name: "Sentadilla",      muscle: "Cuadriceps",     cat: "Fuerza",     pr: "120 kg", scheme: "5×5",  desc: "Ejercicio compuesto de tren inferior. Activa cuádriceps, glúteos e isquiotibiales." },
  { id: 2, name: "Press de Banca",  muscle: "Pecho",          cat: "Fuerza",     pr: "95 kg",  scheme: "5×5",  desc: "Movimiento de empuje horizontal. Principal ejercicio de pecho." },
  { id: 3, name: "Peso Muerto",     muscle: "Isquiotibiales", cat: "Fuerza",     pr: "155 kg", scheme: "3×5",  desc: "Rey de los compuestos. Activa toda la cadena posterior." },
  { id: 4, name: "Press Militar",   muscle: "Hombros",        cat: "Fuerza",     pr: "70 kg",  scheme: "4×6",  desc: "Empuje vertical. Activa deltoides anterior y tríceps." },
  { id: 5, name: "Remo con Barra",  muscle: "Espalda",        cat: "Fuerza",     pr: "90 kg",  scheme: "4×6",  desc: "Tracción horizontal. Desarrolla el grosor de la espalda." },
  { id: 6, name: "Pull-up",         muscle: "Dorsales",       cat: "Calistenia", pr: "+20 kg", scheme: "4×8",  desc: "Tracción vertical. Excelente para amplitud de espalda." },
  { id: 7, name: "Fondos",          muscle: "Tríceps",        cat: "Calistenia", pr: "+25 kg", scheme: "3×10", desc: "Empuje en dips. Activa pecho inferior y tríceps." },
  { id: 8, name: "Curl con Barra",  muscle: "Bíceps",         cat: "Aislamiento",pr: "55 kg",  scheme: "3×12", desc: "Flexión de codo clásica para desarrollo de bíceps." },
];

const ROUTINES = [
  {
    id: 1, name: "Push", label: "Empuje", days: "Lun / Jue", color: "#c8f135",
    exs: [
      { name: "Press de Banca", sets: 5, reps: 5,  kg: 90   },
      { name: "Press Militar",  sets: 4, reps: 6,  kg: 62.5 },
      { name: "Fondos",         sets: 3, reps: 10, kg: 20   },
      { name: "Aperturas",      sets: 3, reps: 12, kg: 18   },
    ],
    last: "Hace 2 días", duration: "~58 min",
  },
  {
    id: 2, name: "Pull", label: "Tracción", days: "Mar / Vie", color: "#4eefc4",
    exs: [
      { name: "Peso Muerto",    sets: 3, reps: 5,  kg: 150 },
      { name: "Remo con Barra", sets: 4, reps: 6,  kg: 90  },
      { name: "Pull-up",        sets: 4, reps: 8,  kg: 20  },
      { name: "Curl con Barra", sets: 3, reps: 12, kg: 55  },
    ],
    last: "Ayer", duration: "~62 min",
  },
  {
    id: 3, name: "Legs", label: "Piernas", days: "Mié / Sáb", color: "#7c6fff",
    exs: [
      { name: "Sentadilla", sets: 5, reps: 5,  kg: 112.5 },
      { name: "Prensa",     sets: 4, reps: 8,  kg: 200   },
      { name: "Zancadas",   sets: 3, reps: 10, kg: 30    },
      { name: "Extensiones",sets: 3, reps: 15, kg: 50    },
    ],
    last: "Hace 4 días", duration: "~71 min",
  },
];

const RANKS = [
  { name: "Bronce",   icon: "🥉", done: true,  current: false, pts: "0–20"   },
  { name: "Plata",    icon: "🥈", done: true,  current: false, pts: "20–40"  },
  { name: "Oro",      icon: "🥇", done: true,  current: false, pts: "40–60"  },
  { name: "Platino",  icon: "💎", done: true,  current: true,  pts: "60–80"  },
  { name: "Diamante", icon: "💠", done: false, current: false, pts: "80–95"  },
  { name: "Élite",    icon: "👑", done: false, current: false, pts: "95–100" },
];

type ChatMsg = { role: "user" | "ai"; text: string };

// ─── Phone shell ─────────────────────────────────────────────────────────────

function Phone({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="relative mx-auto overflow-hidden"
      style={{
        width: 390, height: 844,
        background: "#09090e",
        borderRadius: 48,
        boxShadow: "0 0 0 10px #1a1a26, 0 40px 120px rgba(0,0,0,0.8), 0 0 60px rgba(200,241,53,0.04)",
      }}
    >
      {/* Dynamic island */}
      <div className="absolute top-3.5 left-1/2 -translate-x-1/2 z-50 w-28 h-8 rounded-full bg-black flex items-center justify-center gap-2">
        <div className="w-2.5 h-2.5 rounded-full bg-zinc-800 border border-zinc-700" />
        <div className="w-4 h-4 rounded-full bg-zinc-800 border border-zinc-700" />
      </div>

      {/* Status bar */}
      <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-7 pt-1 z-40" style={{ height: 50 }}>
        <span className="text-xs font-semibold text-foreground" style={MONO}>09:41</span>
        <div className="flex items-center gap-1.5">
          <div className="flex gap-0.5 items-end h-3">
            {[3,4,5,6].map(h => <div key={h} className="w-1 rounded-sm bg-foreground" style={{ height: `${h * 3}px` }} />)}
          </div>
          <svg width="15" height="11" viewBox="0 0 15 11" fill="none">
            <path d="M7.5 2.2C9.7 2.2 11.7 3.1 13.1 4.6L14.5 3.1C12.7 1.2 10.2 0 7.5 0C4.8 0 2.3 1.2 0.5 3.1L1.9 4.6C3.3 3.1 5.3 2.2 7.5 2.2Z" fill="white" />
            <path d="M7.5 5.5C8.9 5.5 10.1 6.1 11 7L12.4 5.5C11.1 4.1 9.4 3.3 7.5 3.3C5.6 3.3 3.9 4.1 2.6 5.5L4 7C4.9 6.1 6.1 5.5 7.5 5.5Z" fill="white" />
            <circle cx="7.5" cy="10" r="1.5" fill="white" />
          </svg>
          <div className="flex items-center gap-0.5">
            <div className="w-6 h-3 border border-white/50 rounded-sm flex items-center px-0.5">
              <div className="bg-primary rounded-sm flex-1 h-2" style={{ width: "80%" }} />
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="absolute inset-0 pt-[50px] pb-0 overflow-hidden" style={{ fontFamily: "'DM Sans', sans-serif" }}>
        {children}
      </div>
    </div>
  );
}

// ─── Shared components ────────────────────────────────────────────────────────

function BottomTabs({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  const tabs: { id: Tab; icon: React.ReactNode; label: string }[] = [
    { id: "home",      icon: <LayoutDashboard size={20} />, label: "Inicio"    },
    { id: "routines",  icon: <ClipboardList size={20} />,  label: "Rutinas"   },
    { id: "exercises", icon: <Dumbbell size={20} />,       label: "Ejercicios"},
    { id: "stats",     icon: <BarChart3 size={20} />,      label: "Stats"     },
    { id: "coach",     icon: <Bot size={20} />,            label: "Coach"     },
  ];
  return (
    <div
      className="absolute bottom-0 left-0 right-0 flex items-stretch"
      style={{ height: 82, background: "#0d0d14", borderTop: "1px solid rgba(255,255,255,0.07)", paddingBottom: 16 }}
    >
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className="flex-1 flex flex-col items-center justify-center gap-1 transition-all"
        >
          <span className={active === t.id ? "text-primary" : "text-muted-foreground"}>{t.icon}</span>
          <span
            className={`text-[10px] font-medium ${active === t.id ? "text-primary" : "text-muted-foreground"}`}
            style={MONO}
          >
            {t.label}
          </span>
          {active === t.id && (
            <span className="absolute bottom-[66px] w-1 h-1 rounded-full bg-primary" />
          )}
          {t.id === "coach" && (
            <span className="absolute mt-[-14px] ml-4 w-2 h-2 rounded-full bg-primary border-2 border-[#0d0d14]" />
          )}
        </button>
      ))}
    </div>
  );
}

function MobileHeader({
  title,
  subtitle,
  right,
  onBack,
}: {
  title?: string;
  subtitle?: string;
  right?: React.ReactNode;
  onBack?: () => void;
}) {
  return (
    <div className="px-5 pt-3 pb-4 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        {onBack && (
          <button onClick={onBack} className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
            <ArrowLeft size={15} className="text-foreground" />
          </button>
        )}
        <div>
          {subtitle && <p className="text-[10px] text-muted-foreground uppercase tracking-widest" style={MONO}>{subtitle}</p>}
          {title && <h2 className="text-2xl font-black uppercase leading-tight" style={DISPLAY}>{title}</h2>}
        </div>
      </div>
      {right}
    </div>
  );
}

function Pill({
  children, active, color,
}: { children: React.ReactNode; active?: boolean; color?: string }) {
  return (
    <span
      className="text-[10px] font-bold px-2 py-0.5 rounded-full"
      style={{
        ...MONO,
        background: color ? `${color}22` : active ? "rgba(200,241,53,0.15)" : "rgba(255,255,255,0.07)",
        color: color ?? (active ? "#c8f135" : "#7a7a96"),
      }}
    >
      {children}
    </span>
  );
}

function ScrollArea({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`overflow-y-auto ${className}`} style={{ scrollbarWidth: "none" }}>
      {children}
    </div>
  );
}

// ─── Splash ───────────────────────────────────────────────────────────────────

function Splash({ onDone }: { onDone: () => void }) {
  useEffect(() => { const t = setTimeout(onDone, 1600); return () => clearTimeout(t); }, []);
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6" style={{ background: "linear-gradient(160deg, #09090e 0%, #0f0f1a 100%)" }}>
      <div className="relative">
        <div className="absolute inset-0 blur-3xl opacity-40 bg-primary rounded-full scale-150" />
        <div className="relative w-20 h-20 rounded-2xl bg-primary flex items-center justify-center shadow-lg">
          <Zap size={40} className="text-primary-foreground" fill="currentColor" />
        </div>
      </div>
      <div className="text-center">
        <h1 className="text-5xl font-black uppercase tracking-[0.15em]" style={DISPLAY}>ZENITH</h1>
        <p className="text-muted-foreground text-sm mt-1">Entrena. Progresa. Domina.</p>
      </div>
      <div className="flex gap-1.5 mt-4">
        {[0,1,2].map(i => (
          <div key={i} className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" style={{ animationDelay: `${i * 0.2}s` }} />
        ))}
      </div>
    </div>
  );
}

// ─── Login ────────────────────────────────────────────────────────────────────

function Login({ onLogin, onRegister }: { onLogin: () => void; onRegister: () => void }) {
  const [showPass, setShowPass] = useState(false);

  return (
    <ScrollArea className="h-full">
      <div className="px-6 pt-8 pb-8 flex flex-col min-h-full">
        {/* Logo */}
        <div className="flex items-center gap-2.5 mb-10">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center">
            <Zap size={18} className="text-primary-foreground" fill="currentColor" />
          </div>
          <span className="text-2xl font-black tracking-[0.15em] uppercase" style={DISPLAY}>ZENITH</span>
        </div>

        <h1 className="text-4xl font-black uppercase leading-tight mb-1" style={DISPLAY}>
          Bienvenido<br />de vuelta
        </h1>
        <p className="text-muted-foreground text-sm mb-8">Inicia sesión para continuar</p>

        <div className="space-y-4 mb-6">
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted-foreground block mb-1.5" style={MONO}>Email</label>
            <input
              defaultValue="carlos@zenith.app"
              className="w-full bg-secondary border border-border rounded-xl px-4 py-3.5 text-sm outline-none focus:border-primary/50 transition-colors"
            />
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted-foreground block mb-1.5" style={MONO}>Contraseña</label>
            <div className="relative">
              <input
                type={showPass ? "text" : "password"}
                defaultValue="Zenith2026!"
                className="w-full bg-secondary border border-border rounded-xl px-4 py-3.5 pr-12 text-sm outline-none focus:border-primary/50 transition-colors"
              />
              <button
                onClick={() => setShowPass(v => !v)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground"
              >
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
        </div>

        <button
          onClick={onLogin}
          className="w-full bg-primary text-primary-foreground rounded-2xl py-4 font-bold text-base active:scale-95 transition-all flex items-center justify-center gap-2 mb-4"
        >
          <Zap size={16} fill="currentColor" /> Entrar
        </button>

        <button className="w-full border border-border rounded-2xl py-4 font-semibold text-sm text-muted-foreground hover:border-white/20 transition-colors mb-8">
          Continuar con Google
        </button>

        <p className="text-center text-sm text-muted-foreground mt-auto">
          ¿Sin cuenta?{" "}
          <button onClick={onRegister} className="text-primary font-semibold">
            Regístrate
          </button>
        </p>
      </div>
    </ScrollArea>
  );
}

// ─── Register ─────────────────────────────────────────────────────────────────

function Register({ onBack, onDone }: { onBack: () => void; onDone: () => void }) {
  const [step, setStep] = useState(1);

  return (
    <ScrollArea className="h-full">
      <div className="px-6 pt-4 pb-8">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={onBack} className="w-9 h-9 rounded-full bg-secondary flex items-center justify-center">
            <ArrowLeft size={16} />
          </button>
          <span className="text-sm font-medium text-muted-foreground">Paso {step} de 2</span>
          <div className="flex gap-1.5 ml-auto">
            <div className={`h-1 w-12 rounded-full transition-all ${step >= 1 ? "bg-primary" : "bg-secondary"}`} />
            <div className={`h-1 w-12 rounded-full transition-all ${step >= 2 ? "bg-primary" : "bg-secondary"}`} />
          </div>
        </div>

        {step === 1 && (
          <>
            <h1 className="text-3xl font-black uppercase mb-1" style={DISPLAY}>Crea tu cuenta</h1>
            <p className="text-muted-foreground text-sm mb-7">Datos básicos de acceso</p>
            <div className="space-y-4 mb-6">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-muted-foreground block mb-1.5" style={MONO}>Nombre</label>
                  <input defaultValue="Carlos" className="w-full bg-secondary border border-border rounded-xl px-4 py-3.5 text-sm outline-none focus:border-primary/50 transition-colors" />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-muted-foreground block mb-1.5" style={MONO}>Apellido</label>
                  <input defaultValue="Mendoza" className="w-full bg-secondary border border-border rounded-xl px-4 py-3.5 text-sm outline-none focus:border-primary/50 transition-colors" />
                </div>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted-foreground block mb-1.5" style={MONO}>Email</label>
                <input defaultValue="carlos@zenith.app" className="w-full bg-secondary border border-border rounded-xl px-4 py-3.5 text-sm outline-none focus:border-primary/50 transition-colors" />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted-foreground block mb-1.5" style={MONO}>Contraseña</label>
                <input type="password" defaultValue="••••••••" className="w-full bg-secondary border border-border rounded-xl px-4 py-3.5 text-sm outline-none focus:border-primary/50 transition-colors" />
              </div>
            </div>
            <button onClick={() => setStep(2)} className="w-full bg-primary text-primary-foreground rounded-2xl py-4 font-bold active:scale-95 transition-all">
              Continuar
            </button>
          </>
        )}

        {step === 2 && (
          <>
            <h1 className="text-3xl font-black uppercase mb-1" style={DISPLAY}>Tu perfil</h1>
            <p className="text-muted-foreground text-sm mb-7">Para personalizar tu entrenamiento</p>
            <div className="space-y-4 mb-6">
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted-foreground block mb-2" style={MONO}>Nivel de experiencia</label>
                <div className="grid grid-cols-3 gap-2">
                  {["Principiante", "Intermedio", "Avanzado"].map((l, i) => (
                    <button key={l} className={`py-2.5 rounded-xl text-xs font-semibold border transition-all ${i === 1 ? "bg-primary/10 border-primary/40 text-primary" : "bg-secondary border-border text-muted-foreground"}`}>
                      {l}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted-foreground block mb-2" style={MONO}>Objetivo principal</label>
                <div className="grid grid-cols-2 gap-2">
                  {["Fuerza", "Hipertrofia", "Resistencia", "Pérdida de peso"].map((l, i) => (
                    <button key={l} className={`py-2.5 rounded-xl text-xs font-semibold border transition-all ${i === 0 ? "bg-primary/10 border-primary/40 text-primary" : "bg-secondary border-border text-muted-foreground"}`}>
                      {l}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[["Peso (kg)", "82"], ["Altura (cm)", "178"], ["Edad", "29"]].map(([l, v]) => (
                  <div key={l}>
                    <label className="text-[10px] uppercase tracking-widest text-muted-foreground block mb-1.5" style={MONO}>{l}</label>
                    <input defaultValue={v} className="w-full bg-secondary border border-border rounded-xl px-3 py-3 text-sm outline-none focus:border-primary/50 transition-colors text-center font-semibold" />
                  </div>
                ))}
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setStep(1)} className="flex-1 border border-border rounded-2xl py-4 font-semibold text-sm text-muted-foreground">
                Atrás
              </button>
              <button onClick={onDone} className="flex-1 bg-primary text-primary-foreground rounded-2xl py-4 font-bold flex items-center justify-center gap-2 active:scale-95 transition-all">
                <Check size={16} /> Crear cuenta
              </button>
            </div>
          </>
        )}
      </div>
    </ScrollArea>
  );
}

// ─── Home screen ──────────────────────────────────────────────────────────────

function HomeScreen({ onStartSession, onRank }: { onStartSession: () => void; onRank: () => void }) {
  const todaySets = [
    { name: "Press de Banca", spec: "5×5 @ 90kg",   done: true  },
    { name: "Press Militar",  spec: "4×6 @ 62.5kg", done: true  },
    { name: "Fondos",         spec: "3×10 +20kg",   done: false },
    { name: "Aperturas",      spec: "3×12 @ 18kg",  done: false },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Fixed header */}
      <div className="px-5 pt-3 pb-2 shrink-0 flex items-center justify-between">
        <div>
          <p className="text-[10px] text-muted-foreground uppercase tracking-widest" style={MONO}>JUE 10 JUL</p>
          <h1 className="text-3xl font-black uppercase leading-tight" style={DISPLAY}>
            Hola, <span className="text-primary">Carlos 👋</span>
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <button className="w-9 h-9 rounded-full bg-secondary flex items-center justify-center">
            <Bell size={16} className="text-muted-foreground" />
          </button>
          <div className="w-9 h-9 rounded-full bg-primary/20 flex items-center justify-center">
            <span className="text-xs font-black text-primary" style={DISPLAY}>CM</span>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1 px-5 pb-2">
        {/* Streak + Rank banner */}
        <div className="flex gap-2.5 mb-5 mt-1">
          <div className="flex-1 bg-card rounded-2xl p-3.5 border border-border flex items-center gap-2.5">
            <Flame size={18} className="text-orange-400 shrink-0" />
            <div>
              <p className="text-xl font-black text-primary leading-none" style={DISPLAY}>18</p>
              <p className="text-[10px] text-muted-foreground" style={MONO}>DÍAS RACHA</p>
            </div>
          </div>
          <button onClick={onRank} className="flex-1 bg-card rounded-2xl p-3.5 border border-border flex items-center gap-2.5">
            <span className="text-xl">💎</span>
            <div>
              <p className="text-sm font-black leading-none">Platino I</p>
              <p className="text-[10px] text-muted-foreground" style={MONO}>74 / 100 PTS</p>
            </div>
            <ChevronRight size={14} className="text-muted-foreground ml-auto" />
          </button>
        </div>

        {/* KPI row */}
        <div className="grid grid-cols-3 gap-2.5 mb-5">
          {[
            { label: "Sesiones", value: "42", unit: "mes",     icon: <Activity size={13} /> },
            { label: "Volumen",  value: "21K", unit: "kg/sem", icon: <TrendingUp size={13} /> },
            { label: "PRs",      value: "8",   unit: "activos",icon: <Zap size={13} /> },
          ].map(k => (
            <div key={k.label} className="bg-card rounded-2xl p-3.5 border border-border">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-muted-foreground">{k.icon}</span>
                <span className="text-[9px] text-muted-foreground uppercase" style={MONO}>{k.label}</span>
              </div>
              <p className="text-2xl font-black leading-none" style={DISPLAY}>{k.value}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">{k.unit}</p>
            </div>
          ))}
        </div>

        {/* Today session card */}
        <div className="bg-card rounded-2xl border border-border overflow-hidden mb-5">
          <div
            className="px-4 py-3 flex items-center justify-between"
            style={{ borderBottom: "1px solid rgba(200,241,53,0.15)", background: "rgba(200,241,53,0.04)" }}
          >
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-0.5" style={MONO}>HOY · PUSH</p>
              <p className="text-base font-black uppercase" style={DISPLAY}>Sesión de empuje</p>
            </div>
            <Pill active>2/4 SERIES</Pill>
          </div>
          <div className="px-4 py-3 space-y-3">
            {todaySets.map((s, i) => (
              <div key={i} className="flex items-center gap-3">
                {s.done
                  ? <CheckCircle2 size={16} className="text-primary shrink-0" />
                  : <Circle size={16} className="text-muted-foreground shrink-0" />}
                <span className={`text-sm flex-1 ${s.done ? "line-through text-muted-foreground" : "font-medium"}`}>{s.name}</span>
                <span className="text-[11px] text-muted-foreground shrink-0" style={MONO}>{s.spec}</span>
              </div>
            ))}
          </div>
          <div className="px-4 pb-4">
            <button
              onClick={onStartSession}
              className="w-full bg-primary text-primary-foreground rounded-xl py-3.5 font-bold text-sm active:scale-95 transition-all flex items-center justify-center gap-2"
            >
              <Play size={15} fill="currentColor" /> Continuar sesión
            </button>
          </div>
        </div>

        {/* Mini volume chart */}
        <div className="bg-card rounded-2xl border border-border p-4 mb-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-black uppercase" style={DISPLAY}>Volumen semanal</p>
            <Pill>8 semanas</Pill>
          </div>
          <ResponsiveContainer width="100%" height={90}>
            <AreaChart data={WEEKLY_VOL} margin={{ top: 5, right: 4, left: -30, bottom: 0 }}>
              <defs>
                <linearGradient id="vg-home" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#c8f135" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#c8f135" stopOpacity={0}    />
                </linearGradient>
              </defs>
              <XAxis dataKey="w" tick={{ fill: "#7a7a96", fontSize: 9 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "#111118", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 8, fontSize: 11 }} itemStyle={{ color: "#c8f135" }} labelStyle={{ color: "#f0f0f5" }} />
              <Area type="monotone" dataKey="v" name="kg" stroke="#c8f135" strokeWidth={2} fill="url(#vg-home)" dot={false} activeDot={{ r: 3, fill: "#c8f135" }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* AI Coach banner */}
        <div
          className="rounded-2xl p-4 flex items-start gap-3"
          style={{ background: "rgba(200,241,53,0.06)", border: "1px solid rgba(200,241,53,0.18)" }}
        >
          <div className="w-9 h-9 rounded-full bg-primary/15 flex items-center justify-center shrink-0">
            <Sparkles size={15} className="text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold mb-1">
              Sentadilla: <span className="text-primary">+2.5 kg esta semana</span>
            </p>
            <p className="text-xs text-muted-foreground leading-relaxed">RPE &lt; 8 en 2 sesiones seguidas. Progresión segura detectada.</p>
          </div>
        </div>

        <div className="h-5" />
      </ScrollArea>
    </div>
  );
}

// ─── Routines screen ──────────────────────────────────────────────────────────

function RoutinesScreen({ onStart, onDetail }: { onStart: (r: typeof ROUTINES[0]) => void; onDetail: (r: typeof ROUTINES[0]) => void }) {
  const history = [
    { date: "Mar 8 Jul", name: "Pull", dur: "62 min", vol: "9,240", color: "#4eefc4" },
    { date: "Lun 7 Jul", name: "Legs", dur: "71 min", vol: "11,400", color: "#7c6fff" },
    { date: "Sáb 5 Jul", name: "Push", dur: "58 min", vol: "8,900",  color: "#c8f135" },
  ];

  return (
    <div className="flex flex-col h-full">
      <MobileHeader
        title="Rutinas"
        subtitle="Planes activos"
        right={
          <button className="w-9 h-9 rounded-full bg-primary/15 flex items-center justify-center">
            <Plus size={16} className="text-primary" />
          </button>
        }
      />

      <ScrollArea className="flex-1 px-5 pb-2">
        {ROUTINES.map(r => (
          <div
            key={r.id}
            className="bg-card rounded-2xl border border-border mb-3 overflow-hidden"
            style={{ borderLeft: `3px solid ${r.color}` }}
          >
            <div className="p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-xl font-black uppercase leading-tight" style={DISPLAY}>{r.name}</p>
                  <p className="text-xs text-muted-foreground">{r.label} · {r.days}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Pill color={r.color}>{r.last}</Pill>
                </div>
              </div>
              <div className="space-y-1.5 mb-4">
                {r.exs.map((ex, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <span className="w-1 h-1 rounded-full shrink-0" style={{ background: r.color }} />
                    <span className="flex-1 text-xs">{ex.name}</span>
                    <span className="text-[11px] text-muted-foreground" style={MONO}>{ex.sets}×{ex.reps} @ {ex.kg}kg</span>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => onStart(r)}
                  className="flex-1 py-2.5 rounded-xl text-sm font-bold text-primary-foreground flex items-center justify-center gap-1.5 active:scale-95 transition-all"
                  style={{ background: r.color }}
                >
                  <Play size={13} fill="currentColor" className="text-[#09090e]" />
                  <span className="text-[#09090e]">Iniciar</span>
                </button>
                <button
                  onClick={() => onDetail(r)}
                  className="px-4 py-2.5 rounded-xl text-sm font-medium border border-border text-muted-foreground hover:bg-secondary transition-colors"
                >
                  Ver
                </button>
              </div>
            </div>
          </div>
        ))}

        {/* History */}
        <div className="mb-1 mt-2">
          <p className="text-sm font-black uppercase mb-3" style={DISPLAY}>Historial reciente</p>
          <div className="space-y-2">
            {history.map((s, i) => (
              <div key={i} className="bg-card rounded-xl border border-border px-4 py-3 flex items-center gap-3">
                <div className="w-1.5 h-full min-h-8 rounded-full shrink-0" style={{ background: s.color }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold">{s.name}</p>
                  <p className="text-[11px] text-muted-foreground" style={MONO}>{s.date} · {s.dur}</p>
                </div>
                <span className="text-xs font-bold text-muted-foreground" style={MONO}>{s.vol} kg</span>
                <ChevronRight size={14} className="text-muted-foreground" />
              </div>
            ))}
          </div>
        </div>

        <div className="h-5" />
      </ScrollArea>
    </div>
  );
}

// ─── Exercises screen ─────────────────────────────────────────────────────────

function ExercisesScreen({ onDetail }: { onDetail: (ex: typeof EXERCISES[0]) => void }) {
  const [cat, setCat] = useState("Todos");
  const [search, setSearch] = useState("");
  const cats = ["Todos", "Fuerza", "Calistenia", "Aislamiento"];
  const filtered = EXERCISES.filter(e =>
    (cat === "Todos" || e.cat === cat) &&
    (search === "" || e.name.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="flex flex-col h-full">
      <MobileHeader
        title="Ejercicios"
        subtitle={`${EXERCISES.length} en catálogo`}
        right={
          <button className="w-9 h-9 rounded-full bg-primary/15 flex items-center justify-center">
            <Plus size={16} className="text-primary" />
          </button>
        }
      />

      {/* Search */}
      <div className="px-5 mb-3 shrink-0">
        <div className="bg-secondary rounded-xl flex items-center gap-2 px-3 border border-border">
          <Search size={15} className="text-muted-foreground shrink-0" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar ejercicio..."
            className="flex-1 bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
      </div>

      {/* Category filter */}
      <div className="flex gap-2 px-5 mb-4 shrink-0 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
        {cats.map(c => (
          <button
            key={c}
            onClick={() => setCat(c)}
            className={`px-3.5 py-1.5 rounded-full text-xs font-bold shrink-0 transition-all ${cat === c ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground border border-border"}`}
          >
            {c}
          </button>
        ))}
      </div>

      <ScrollArea className="flex-1 px-5 pb-2">
        <div className="space-y-2">
          {filtered.map(ex => (
            <button
              key={ex.id}
              onClick={() => onDetail(ex)}
              className="w-full bg-card rounded-2xl border border-border p-4 flex items-center gap-3 active:scale-[0.98] transition-all text-left"
            >
              <div className="w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                <Dumbbell size={18} className="text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold">{ex.name}</p>
                <p className="text-[11px] text-muted-foreground">{ex.muscle}</p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <Pill>{ex.cat}</Pill>
                <span className="text-xs font-bold text-primary" style={MONO}>PR {ex.pr}</span>
              </div>
              <ChevronRight size={15} className="text-muted-foreground shrink-0" />
            </button>
          ))}
        </div>
        <div className="h-5" />
      </ScrollArea>
    </div>
  );
}

// ─── Exercise detail ──────────────────────────────────────────────────────────

function ExerciseDetail({ ex, onBack }: { ex: typeof EXERCISES[0]; onBack: () => void }) {
  const prog = [
    { d: "May 1", v: 80 }, { d: "May 15", v: 85 }, { d: "Jun 1", v: 87.5 },
    { d: "Jun 8", v: 90 }, { d: "Jun 22", v: 92.5 }, { d: "Jul 1", v: 95 },
  ];

  return (
    <div className="flex flex-col h-full">
      <MobileHeader onBack={onBack} />
      <ScrollArea className="flex-1 px-5 pb-2">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
            <Dumbbell size={24} className="text-primary" />
          </div>
          <div>
            <h2 className="text-2xl font-black uppercase" style={DISPLAY}>{ex.name}</h2>
            <p className="text-sm text-muted-foreground">{ex.muscle} · {ex.cat}</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2.5 mb-5">
          {[
            { l: "PR actual", v: ex.pr, accent: true },
            { l: "Esquema", v: ex.scheme, accent: false },
            { l: "Sets/semana", v: "12", accent: false },
          ].map(m => (
            <div key={m.l} className="bg-card rounded-xl border border-border p-3 text-center">
              <p className={`text-xl font-black leading-none ${m.accent ? "text-primary" : ""}`} style={DISPLAY}>{m.v}</p>
              <p className="text-[10px] text-muted-foreground mt-1">{m.l}</p>
            </div>
          ))}
        </div>

        <div className="bg-card rounded-2xl border border-border p-4 mb-4">
          <p className="text-sm font-black uppercase mb-3" style={DISPLAY}>Progresión de carga</p>
          <ResponsiveContainer width="100%" height={100}>
            <AreaChart data={prog} margin={{ top: 5, right: 4, left: -28, bottom: 0 }}>
              <defs>
                <linearGradient id="exg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#c8f135" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#c8f135" stopOpacity={0}   />
                </linearGradient>
              </defs>
              <XAxis dataKey="d" tick={{ fill: "#7a7a96", fontSize: 9 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "#111118", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 8, fontSize: 11 }} itemStyle={{ color: "#c8f135" }} labelStyle={{ color: "#f0f0f5" }} />
              <Area type="monotone" dataKey="v" name="kg" stroke="#c8f135" strokeWidth={2} fill="url(#exg)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card rounded-2xl border border-border p-4 mb-4">
          <p className="text-sm font-black uppercase mb-2" style={DISPLAY}>Descripción</p>
          <p className="text-sm text-muted-foreground leading-relaxed">{ex.desc}</p>
        </div>

        <button className="w-full bg-primary text-primary-foreground rounded-2xl py-4 font-bold text-sm active:scale-95 transition-all flex items-center justify-center gap-2">
          <Plus size={15} /> Añadir a rutina
        </button>
        <div className="h-5" />
      </ScrollArea>
    </div>
  );
}

// ─── Stats screen ─────────────────────────────────────────────────────────────

function StatsScreen() {
  const [period, setPeriod] = useState("8S");

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 pt-3 pb-2 flex items-center justify-between shrink-0">
        <div>
          <p className="text-[10px] text-muted-foreground uppercase tracking-widest" style={MONO}>ANÁLISIS</p>
          <h2 className="text-2xl font-black uppercase" style={DISPLAY}>Estadísticas</h2>
        </div>
        <div className="flex gap-1">
          {["4S","8S","3M"].map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all ${period === p ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"}`}
              style={MONO}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <ScrollArea className="flex-1 px-5 pb-2">
        <div className="grid grid-cols-2 gap-2.5 mb-4">
          {[
            { l: "Volumen", v: "87,400", u: "kg total", delta: "+23%",    icon: <TrendingUp size={13} /> },
            { l: "Series",  v: "312",    u: "sets",      delta: "+18 vs ant", icon: <Layers size={13} /> },
            { l: "Entreno", v: "14.2",   u: "horas",    delta: "+2.1h",   icon: <Clock size={13} /> },
            { l: "PRs",     v: "8",      u: "ejercicios",delta: "+3 nuevos", icon: <Star size={13} /> },
          ].map(k => (
            <div key={k.l} className="bg-card rounded-2xl border border-border p-3.5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-muted-foreground">{k.icon}</span>
                <span className="text-[9px] text-muted-foreground uppercase" style={MONO}>{k.l}</span>
              </div>
              <p className="text-2xl font-black leading-none mb-0.5" style={DISPLAY}>{k.v}</p>
              <p className="text-[10px] text-muted-foreground">{k.u}</p>
              <div className="flex items-center gap-0.5 mt-1.5">
                <ArrowUp size={10} className="text-primary" />
                <span className="text-[10px] text-primary font-medium">{k.delta}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="bg-card rounded-2xl border border-border p-4 mb-3">
          <p className="text-sm font-black uppercase mb-3" style={DISPLAY}>Volumen semanal</p>
          <ResponsiveContainer width="100%" height={110}>
            <AreaChart data={WEEKLY_VOL} margin={{ top: 5, right: 4, left: -30, bottom: 0 }}>
              <defs>
                <linearGradient id="vg-stats" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#c8f135" stopOpacity={0.22} />
                  <stop offset="95%" stopColor="#c8f135" stopOpacity={0}    />
                </linearGradient>
              </defs>
              <XAxis dataKey="w" tick={{ fill: "#7a7a96", fontSize: 9 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "#111118", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 8, fontSize: 11 }} itemStyle={{ color: "#c8f135" }} labelStyle={{ color: "#f0f0f5" }} />
              <Area type="monotone" dataKey="v" name="kg" stroke="#c8f135" strokeWidth={2} fill="url(#vg-stats)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card rounded-2xl border border-border p-4 mb-3">
          <p className="text-sm font-black uppercase mb-3" style={DISPLAY}>Series por músculo</p>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={MUSCLE_DATA} margin={{ top: 0, right: 4, left: -30, bottom: 0 }}>
              <XAxis dataKey="g" tick={{ fill: "#7a7a96", fontSize: 9 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "#111118", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 8, fontSize: 11 }} itemStyle={{ color: "#c8f135" }} labelStyle={{ color: "#f0f0f5" }} />
              <Bar dataKey="s" name="Series" fill="#c8f135" opacity={0.85} radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Lifts progression */}
        <div className="bg-card rounded-2xl border border-border p-4 mb-3">
          <p className="text-sm font-black uppercase mb-3" style={DISPLAY}>Levantamientos principales</p>
          {[
            { name: "Sentadilla",    pr: "115 kg", delta: "+15 kg", pct: 78, color: "#c8f135" },
            { name: "Press Banca",   pr: "92.5 kg",delta: "+12.5 kg",pct: 62, color: "#4eefc4" },
            { name: "Peso Muerto",   pr: "155 kg", delta: "+25 kg", pct: 85, color: "#7c6fff" },
          ].map(l => (
            <div key={l.name} className="mb-3 last:mb-0">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-semibold">{l.name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-primary flex items-center gap-0.5">
                    <ArrowUp size={10} />{l.delta}
                  </span>
                  <span className="text-sm font-bold" style={MONO}>{l.pr}</span>
                </div>
              </div>
              <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${l.pct}%`, background: l.color }} />
              </div>
            </div>
          ))}
        </div>

        <div className="h-5" />
      </ScrollArea>
    </div>
  );
}

// ─── Coach screen ─────────────────────────────────────────────────────────────

function CoachScreen() {
  const [tab, setTab] = useState<"chat" | "sug" | "plan">("chat");
  const [msgs, setMsgs] = useState<ChatMsg[]>([
    { role: "ai", text: "Hola Carlos 👋 Esta semana: 4 sesiones, 21,300 kg de volumen. Tu sentadilla mejoró 5 kg. ¿En qué te ayudo hoy?" },
  ]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const AI_SUGGESTIONS_LOCAL = [
    { id: 1, ex: "Sentadilla",     cur: "5×5 @ 112.5", sug: "5×5 @ 115 kg",  why: "RPE < 8 en 2 sesiones seguidas.",        status: "pending"  as const },
    { id: 2, ex: "Press de Banca", cur: "5×5 @ 90 kg",  sug: "5×5 @ 92.5 kg", why: "Progresión lineal estable confirmada.", status: "pending"  as const },
    { id: 3, ex: "Peso Muerto",    cur: "3×5 @ 150 kg", sug: "Deload parcial", why: "6 semanas de progresión continua.",     status: "accepted" as const },
  ];

  const [suggestions, setSuggestions] = useState(AI_SUGGESTIONS_LOCAL);

  const send = () => {
    if (!input.trim()) return;
    const text = input;
    setInput("");
    setMsgs(m => [...m, { role: "user", text }]);
    setTimeout(() => {
      setMsgs(m => [...m, { role: "ai", text: "Basado en tus datos: mantén la progresión y añade movilidad los domingos para optimizar la recuperación entre sesiones de piernas." }]);
    }, 700);
  };

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 pt-3 pb-0 shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest" style={MONO}>IA PERSONAL</p>
            <h2 className="text-2xl font-black uppercase" style={DISPLAY}>Coach IA</h2>
          </div>
          <div className="w-9 h-9 rounded-full bg-primary/15 flex items-center justify-center">
            <Sparkles size={15} className="text-primary" />
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 border-b border-border mb-0">
          {[
            { id: "chat" as const, label: "Chat" },
            { id: "sug"  as const, label: `Sugerencias ${suggestions.filter(s => s.status === "pending").length > 0 ? `(${suggestions.filter(s => s.status === "pending").length})` : ""}` },
            { id: "plan" as const, label: "Plan" },
          ].map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex-1 py-2 text-xs font-bold border-b-2 -mb-px transition-colors ${tab === t.id ? "border-primary text-primary" : "border-transparent text-muted-foreground"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === "chat" && (
        <>
          <ScrollArea className="flex-1 px-5 pt-3">
            <div className="space-y-3">
              {msgs.map((m, i) => (
                <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${m.role === "ai" ? "bg-primary/15" : "bg-secondary"}`}>
                    {m.role === "ai" ? <Sparkles size={11} className="text-primary" /> : <User size={11} />}
                  </div>
                  <div className={`text-xs rounded-2xl px-3.5 py-2.5 max-w-[75%] leading-relaxed ${m.role === "ai" ? "bg-secondary text-foreground" : "bg-primary text-primary-foreground"}`}>
                    {m.text}
                  </div>
                </div>
              ))}
              <div ref={endRef} />
            </div>
            <div className="flex flex-wrap gap-2 mt-3 mb-2">
              {["¿Cuándo hacer deload?", "Variaciones de sentadilla"].map(p => (
                <button key={p} onClick={() => setInput(p)} className="text-[11px] bg-secondary border border-border rounded-full px-3 py-1.5 text-muted-foreground">
                  {p}
                </button>
              ))}
            </div>
          </ScrollArea>
          <div className="px-5 pb-3 pt-2 shrink-0 flex gap-2" style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && send()}
              placeholder="Pregunta a tu coach..."
              className="flex-1 bg-secondary border border-border rounded-2xl px-4 py-2.5 text-sm outline-none focus:border-primary/50 placeholder:text-muted-foreground"
            />
            <button onClick={send} disabled={!input.trim()} className="w-10 h-10 bg-primary rounded-2xl flex items-center justify-center disabled:opacity-40 active:scale-95 transition-all">
              <Send size={14} className="text-primary-foreground" />
            </button>
          </div>
        </>
      )}

      {tab === "sug" && (
        <ScrollArea className="flex-1 px-5 pt-3 pb-2">
          <div className="space-y-3">
            {suggestions.map(s => (
              <div
                key={s.id}
                className={`bg-card rounded-2xl border p-4 ${s.status === "accepted" ? "border-primary/25" : s.status === "rejected" ? "border-border opacity-50" : "border-border"}`}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <p className="text-sm font-bold">{s.ex}</p>
                  {s.status === "pending"  && <Pill>NUEVA</Pill>}
                  {s.status === "accepted" && <Pill active>ACEPTADA</Pill>}
                  {s.status === "rejected" && <Pill>RECHAZADA</Pill>}
                </div>
                <div className="flex items-center gap-2 text-xs mb-2 flex-wrap">
                  <span className="text-muted-foreground line-through" style={MONO}>{s.cur}</span>
                  <ChevronRight size={10} className="text-muted-foreground" />
                  <span className="text-primary font-bold" style={MONO}>{s.sug}</span>
                </div>
                <p className="text-[11px] text-muted-foreground mb-3">{s.why}</p>
                {s.status === "pending" && (
                  <div className="flex gap-2">
                    <button onClick={() => setSuggestions(p => p.map(sg => sg.id === s.id ? { ...sg, status: "accepted" } : sg))} className="flex-1 bg-primary/10 text-primary border border-primary/25 rounded-xl py-2 text-xs font-bold flex items-center justify-center gap-1 active:scale-95 transition-all">
                      <Check size={12} /> Aceptar
                    </button>
                    <button onClick={() => setSuggestions(p => p.map(sg => sg.id === s.id ? { ...sg, status: "rejected" } : sg))} className="flex-1 bg-secondary border border-border rounded-xl py-2 text-xs font-medium text-muted-foreground flex items-center justify-center gap-1 active:scale-95 transition-all">
                      <X size={12} /> Ignorar
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="h-5" />
        </ScrollArea>
      )}

      {tab === "plan" && (
        <ScrollArea className="flex-1 px-5 pt-3 pb-2">
          <div className="bg-primary/5 border border-primary/20 rounded-2xl p-4 mb-3 flex items-start gap-3">
            <Sparkles size={15} className="text-primary mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-bold mb-0.5">Plan Adaptativo · Semana 9</p>
              <p className="text-xs text-muted-foreground leading-relaxed">Optimizado para balance intensidad ↔ volumen basado en 8 semanas de datos.</p>
            </div>
          </div>

          <div className="space-y-2 mb-4">
            {[
              { day: "Lun", focus: "Push — Intensidad",  note: "+2.5kg Banca", hi: true  },
              { day: "Mar", focus: "Pull — Volumen",     note: "+1 serie Remo", hi: false },
              { day: "Mié", focus: "Descanso activo",    note: "Movilidad",    hi: false },
              { day: "Jue", focus: "Legs — Intensidad",  note: "+2.5kg Squat", hi: true  },
              { day: "Vie", focus: "Pull — Técnica",     note: "ROM completo", hi: false },
              { day: "Sáb", focus: "Push — Volumen",     note: "+1 serie",     hi: false },
              { day: "Dom", focus: "Descanso",           note: "Recuperación", hi: false },
            ].map(d => (
              <div key={d.day} className={`bg-card rounded-xl border px-4 py-3 flex items-center gap-3 ${d.hi ? "border-primary/20" : "border-border"}`}>
                <span className="text-[11px] font-bold text-muted-foreground w-7 shrink-0" style={MONO}>{d.day}</span>
                <span className="text-xs font-medium flex-1">{d.focus}</span>
                <span className={`text-[11px] ${d.hi ? "text-primary font-medium" : "text-muted-foreground"}`}>{d.note}</span>
                {d.hi && <Zap size={12} className="text-primary shrink-0" />}
              </div>
            ))}
          </div>

          <button className="w-full border border-primary/25 text-primary rounded-2xl py-3.5 text-sm font-bold flex items-center justify-center gap-2 active:scale-95 transition-all">
            <RefreshCw size={13} /> Regenerar con IA
          </button>
          <div className="h-5" />
        </ScrollArea>
      )}
    </div>
  );
}

// ─── Rank screen ──────────────────────────────────────────────────────────────

function RankScreen({ onBack }: { onBack: () => void }) {
  return (
    <div className="flex flex-col h-full">
      <MobileHeader title="Rango" subtitle="Progresión" onBack={onBack} />
      <ScrollArea className="flex-1 px-5 pb-2">
        {/* Hero */}
        <div
          className="rounded-2xl p-5 mb-4 relative overflow-hidden"
          style={{ background: "linear-gradient(135deg, #131318 0%, #1a1a28 100%)", border: "1px solid rgba(200,241,53,0.15)" }}
        >
          <div className="absolute top-0 right-0 text-[100px] leading-none opacity-5 font-black select-none" style={DISPLAY}>74</div>
          <div className="relative flex items-start gap-4">
            <span className="text-5xl">💎</span>
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-0.5" style={MONO}>RANGO ACTUAL</p>
              <h3 className="text-3xl font-black uppercase" style={DISPLAY}>Platino I</h3>
              <div className="flex items-baseline gap-1.5 mt-1">
                <span className="text-4xl font-black text-primary" style={DISPLAY}>74</span>
                <span className="text-muted-foreground text-sm">/ 100 pts</span>
              </div>
            </div>
          </div>
          <div className="mt-4">
            <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1.5">
              <span>Platino I</span><span style={MONO}>6 pts para Platino II</span><span>Platino II</span>
            </div>
            <div className="h-2 bg-secondary rounded-full overflow-hidden">
              <div className="h-full bg-primary rounded-full" style={{ width: "70%" }} />
            </div>
          </div>
        </div>

        {/* Ranks */}
        <p className="text-sm font-black uppercase mb-3" style={DISPLAY}>Escala completa</p>
        <div className="space-y-2 mb-4">
          {RANKS.map((r, i) => {
            const pct = r.current ? 70 : r.done ? 100 : 0;
            return (
              <div key={i} className={`bg-card rounded-xl border border-border px-4 py-3 flex items-center gap-3 ${!r.done && !r.current ? "opacity-40" : ""}`}>
                <span className="text-xl">{r.icon}</span>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-sm font-bold ${r.current ? "text-primary" : ""}`}>
                      {r.name}
                      {r.current && <span className="ml-1.5 text-[9px] bg-primary/15 text-primary px-1.5 py-0.5 rounded-full" style={MONO}>ACTUAL</span>}
                    </span>
                    <span className="text-[10px] text-muted-foreground" style={MONO}>{r.pts}</span>
                  </div>
                  <div className="h-1 bg-secondary rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: r.current ? "#c8f135" : r.done ? "#4eefc4" : "#333" }} />
                  </div>
                </div>
                {!r.done && !r.current && <Lock size={12} className="text-muted-foreground" />}
              </div>
            );
          })}
        </div>

        {/* Score breakdown */}
        <p className="text-sm font-black uppercase mb-3" style={DISPLAY}>Composición del score</p>
        <div className="space-y-3 mb-4">
          {[
            { l: "Progresión de carga", v: 21, max: 30, c: "#c8f135" },
            { l: "Consistencia",        v: 18, max: 25, c: "#4eefc4" },
            { l: "Volumen acumulado",   v: 19, max: 25, c: "#7c6fff" },
            { l: "Variedad muscular",   v: 16, max: 20, c: "#f1b535" },
          ].map(s => (
            <div key={s.l}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-medium">{s.l}</span>
                <span className="text-base font-black leading-none" style={{ ...DISPLAY, color: s.c }}>
                  {s.v}<span className="text-xs text-muted-foreground font-normal">/{s.max}</span>
                </span>
              </div>
              <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${(s.v/s.max)*100}%`, background: s.c }} />
              </div>
            </div>
          ))}
        </div>

        <button className="w-full border border-border text-muted-foreground rounded-2xl py-3.5 text-xs font-bold flex items-center justify-center gap-2 active:scale-95 transition-all">
          <RefreshCw size={12} /> Recalcular score
        </button>
        <div className="h-5" />
      </ScrollArea>
    </div>
  );
}

// ─── Active session ───────────────────────────────────────────────────────────

function ActiveSession({ routine, onFinish }: { routine: typeof ROUTINES[0]; onFinish: () => void }) {
  const [exIdx, setExIdx] = useState(0);
  const [setIdx, setSetIdx] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [resting, setResting] = useState(false);
  const [restSec, setRestSec] = useState(0);
  const [kg, setKg] = useState(routine.exs[0].kg);
  const [reps, setReps] = useState(routine.exs[0].reps);
  const [done, setDone] = useState<{ ex: string; set: number; kg: number; reps: number }[]>([]);

  useEffect(() => {
    const t = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!resting || restSec <= 0) { if (resting && restSec <= 0) setResting(false); return; }
    const t = setInterval(() => setRestSec(s => { if (s <= 1) { setResting(false); return 0; } return s - 1; }), 1000);
    return () => clearInterval(t);
  }, [resting, restSec]);

  const fmt = (s: number) => `${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`;
  const ex = routine.exs[exIdx];
  const progress = done.length / routine.exs.reduce((a, e) => a + e.sets, 0);

  const logSet = () => {
    setDone(d => [...d, { ex: ex.name, set: setIdx + 1, kg, reps }]);
    setResting(true);
    setRestSec(120);

    const nextSet = setIdx + 1;
    if (nextSet < ex.sets) {
      setSetIdx(nextSet);
    } else {
      const nextEx = exIdx + 1;
      if (nextEx < routine.exs.length) {
        setExIdx(nextEx);
        setSetIdx(0);
        setKg(routine.exs[nextEx].kg);
        setReps(routine.exs[nextEx].reps);
      } else {
        setTimeout(onFinish, 600);
      }
    }
  };

  return (
    <div className="h-full flex flex-col" style={{ fontFamily: "'DM Sans', sans-serif" }}>
      {/* Header */}
      <div className="px-5 pt-3 pb-3 shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              <span className="text-[10px] text-primary uppercase font-bold" style={MONO}>EN SESIÓN</span>
            </div>
            <p className="text-xl font-black uppercase leading-tight" style={DISPLAY}>{routine.name} · {routine.label}</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-black text-primary leading-none" style={DISPLAY}>{fmt(elapsed)}</p>
            <p className="text-[10px] text-muted-foreground">duración</p>
          </div>
        </div>
        {/* Progress bar */}
        <div className="mt-2.5 h-1 bg-secondary rounded-full overflow-hidden">
          <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${progress * 100}%` }} />
        </div>
      </div>

      {/* Exercise list - mini */}
      <div className="flex gap-2 px-5 py-2.5 shrink-0 overflow-x-auto" style={{ scrollbarWidth: "none", borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
        {routine.exs.map((e, i) => {
          const exDone = done.filter(d => d.ex === e.name).length >= e.sets;
          return (
            <button
              key={i}
              onClick={() => { setExIdx(i); setSetIdx(0); setKg(e.kg); setReps(e.reps); }}
              className={`shrink-0 px-3 py-1.5 rounded-full text-[11px] font-bold transition-all border ${
                i === exIdx ? "border-primary text-primary bg-primary/10"
                  : exDone ? "border-border text-muted-foreground line-through bg-secondary"
                  : "border-border text-muted-foreground bg-secondary"
              }`}
            >
              {e.name.split(" ")[0]}
            </button>
          );
        })}
      </div>

      {/* Main */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 gap-6">
        {resting ? (
          <div className="flex flex-col items-center gap-4">
            <div
              className="w-32 h-32 rounded-full flex flex-col items-center justify-center"
              style={{ border: "3px solid rgba(200,241,53,0.25)", boxShadow: "0 0 40px rgba(200,241,53,0.08)" }}
            >
              <span className="text-5xl font-black text-primary leading-none" style={DISPLAY}>{restSec}</span>
              <span className="text-[10px] text-muted-foreground mt-1" style={MONO}>DESCANSO</span>
            </div>
            <button onClick={() => setResting(false)} className="text-xs text-muted-foreground flex items-center gap-1.5">
              <SkipForward size={12} /> Saltar descanso
            </button>
          </div>
        ) : (
          <>
            <div className="text-center">
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1" style={MONO}>SERIE {setIdx + 1} DE {ex.sets}</p>
              <h3 className="text-4xl font-black uppercase" style={DISPLAY}>{ex.name}</h3>
              <p className="text-muted-foreground text-sm">{ex.muscle ?? ""}</p>
            </div>

            <div className="flex gap-8">
              {/* KG */}
              <div className="flex flex-col items-center gap-3">
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest" style={MONO}>Peso</span>
                <button onClick={() => setKg(v => v + 2.5)} className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center active:scale-90 transition-all">
                  <ChevronUp size={18} />
                </button>
                <span className="text-4xl font-black w-20 text-center leading-none" style={DISPLAY}>{kg}</span>
                <button onClick={() => setKg(v => Math.max(0, v - 2.5))} className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center active:scale-90 transition-all">
                  <ChevronDown size={18} />
                </button>
                <span className="text-xs text-muted-foreground" style={MONO}>kg</span>
              </div>

              <div className="w-px bg-border" />

              {/* Reps */}
              <div className="flex flex-col items-center gap-3">
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest" style={MONO}>Reps</span>
                <button onClick={() => setReps(v => v + 1)} className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center active:scale-90 transition-all">
                  <ChevronUp size={18} />
                </button>
                <span className="text-4xl font-black w-16 text-center leading-none" style={DISPLAY}>{reps}</span>
                <button onClick={() => setReps(v => Math.max(1, v - 1))} className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center active:scale-90 transition-all">
                  <ChevronDown size={18} />
                </button>
                <span className="text-xs text-muted-foreground" style={MONO}>reps</span>
              </div>
            </div>

            <button
              onClick={logSet}
              className="w-full bg-primary text-primary-foreground rounded-2xl py-4 font-black text-base active:scale-95 transition-all flex items-center justify-center gap-2"
            >
              <Check size={18} /> REGISTRAR SERIE
            </button>
          </>
        )}
      </div>

      {/* Done sets mini log */}
      {done.filter(d => d.ex === ex.name).length > 0 && (
        <div className="px-5 pb-3 shrink-0">
          <div className="flex gap-2 flex-wrap">
            {done.filter(d => d.ex === ex.name).map((d, i) => (
              <div key={i} className="bg-primary/10 border border-primary/25 rounded-lg px-2.5 py-1.5 text-[11px] text-primary flex items-center gap-1" style={MONO}>
                <Check size={9} /> {d.reps}×{d.kg}kg
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Finish */}
      <div className="px-5 pb-4 shrink-0" style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <button onClick={onFinish} className="w-full border border-destructive/30 text-destructive rounded-2xl py-3 text-sm font-bold active:scale-95 transition-all flex items-center justify-center gap-2">
          Terminar sesión
        </button>
      </div>
    </div>
  );
}

// ─── Session summary ──────────────────────────────────────────────────────────

function SessionSummary({ routine, onDone }: { routine: typeof ROUTINES[0]; onDone: () => void }) {
  return (
    <div className="flex flex-col h-full" style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <div className="px-5 pt-3 pb-2 shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-0.5" style={MONO}>SESIÓN COMPLETADA</p>
            <h2 className="text-2xl font-black uppercase" style={DISPLAY}>{routine.name} · {routine.label}</h2>
          </div>
          <span className="text-3xl">🏆</span>
        </div>
      </div>

      <ScrollArea className="flex-1 px-5 pb-2">
        {/* Metrics */}
        <div className="grid grid-cols-3 gap-2.5 mb-4">
          {[
            { l: "Duración", v: "58", u: "min" },
            { l: "Volumen",  v: "8,900", u: "kg" },
            { l: "Series",   v: "15", u: "total" },
          ].map(m => (
            <div key={m.l} className="bg-card rounded-2xl border border-border p-3.5 text-center">
              <p className="text-2xl font-black text-primary leading-none" style={DISPLAY}>{m.v}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">{m.u}</p>
              <p className="text-[9px] text-muted-foreground mt-0.5 uppercase" style={MONO}>{m.l}</p>
            </div>
          ))}
        </div>

        {/* PR badge */}
        <div className="bg-card border border-yellow-500/25 rounded-2xl px-4 py-3 flex items-center gap-3 mb-4">
          <Star size={16} className="text-yellow-400 shrink-0" />
          <div>
            <p className="text-sm font-bold"><span className="text-yellow-400">Nuevo PR: </span>Press Militar</p>
            <p className="text-[11px] text-muted-foreground" style={MONO}>65 kg · Serie 3 · RPE 8</p>
          </div>
        </div>

        {/* AI Summary */}
        <div
          className="rounded-2xl p-4 mb-4"
          style={{ background: "rgba(200,241,53,0.05)", border: "1px solid rgba(200,241,53,0.18)" }}
        >
          <div className="flex items-center gap-2 mb-2.5">
            <Sparkles size={14} className="text-primary" />
            <p className="text-sm font-bold text-primary">Análisis del Coach IA</p>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Buena sesión, Carlos. Completaste el 94% del volumen planificado. El Press Militar fue tu punto fuerte — técnica limpia en todas las series y nuevo PR.
          </p>
          <p className="text-xs text-muted-foreground leading-relaxed mt-2">
            Recomendación: duerme 8h, proteína post-entreno. Tu Pull de mañana está priorizado — volumen de espalda ligeramente bajo esta semana.
          </p>
        </div>

        {/* Exercise breakdown */}
        <p className="text-sm font-black uppercase mb-2" style={DISPLAY}>Desglose</p>
        <div className="space-y-2 mb-4">
          {routine.exs.map((ex, i) => (
            <div key={i} className="bg-card rounded-xl border border-border px-4 py-3 flex items-center gap-3">
              <CheckCircle2 size={14} className="text-primary shrink-0" />
              <span className="text-xs font-medium flex-1">{ex.name}</span>
              <span className="text-[11px] text-muted-foreground" style={MONO}>{ex.sets}×{ex.reps} @ {ex.kg}kg</span>
              <span className="text-[11px] text-primary font-bold" style={MONO}>{(ex.sets * ex.reps * ex.kg).toLocaleString()} kg</span>
            </div>
          ))}
        </div>

        <div className="flex gap-3">
          <button onClick={onDone} className="flex-1 bg-primary text-primary-foreground rounded-2xl py-4 font-bold text-sm active:scale-95 transition-all flex items-center justify-center gap-2">
            <Check size={15} /> Guardar sesión
          </button>
          <button className="px-4 border border-border rounded-2xl text-muted-foreground text-sm font-medium flex items-center gap-1.5">
            <Bot size={14} /> Coach
          </button>
        </div>
        <div className="h-5" />
      </ScrollArea>
    </div>
  );
}

// ─── Routine detail ───────────────────────────────────────────────────────────

function RoutineDetail({ routine, onBack, onStart }: { routine: typeof ROUTINES[0]; onBack: () => void; onStart: () => void }) {
  return (
    <div className="flex flex-col h-full">
      <div className="px-5 pt-3 pb-0 shrink-0 flex items-center gap-3">
        <button onClick={onBack} className="w-9 h-9 rounded-full bg-secondary flex items-center justify-center shrink-0">
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] text-muted-foreground uppercase tracking-widest" style={MONO}>RUTINA</p>
          <h2 className="text-2xl font-black uppercase" style={DISPLAY}>{routine.name} · {routine.label}</h2>
        </div>
      </div>

      <ScrollArea className="flex-1 px-5 pt-4 pb-2">
        {/* Info row */}
        <div className="grid grid-cols-2 gap-2.5 mb-5">
          {[
            { l: "Días", v: routine.days },
            { l: "Duración", v: routine.duration },
            { l: "Última vez", v: routine.last },
            { l: "Ejercicios", v: `${routine.exs.length} movimientos` },
          ].map(m => (
            <div key={m.l} className="bg-card rounded-xl border border-border p-3">
              <p className="text-[10px] text-muted-foreground uppercase mb-0.5" style={MONO}>{m.l}</p>
              <p className="text-sm font-semibold">{m.v}</p>
            </div>
          ))}
        </div>

        <p className="text-sm font-black uppercase mb-3" style={DISPLAY}>Ejercicios</p>
        <div className="space-y-2.5 mb-5">
          {routine.exs.map((ex, i) => (
            <div key={i} className="bg-card rounded-2xl border border-border p-4 flex items-center gap-3">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center text-base font-black shrink-0"
                style={{ ...DISPLAY, background: `${routine.color}22`, color: routine.color }}
              >
                {i + 1}
              </div>
              <div className="flex-1">
                <p className="text-sm font-bold">{ex.name}</p>
                <p className="text-[11px] text-muted-foreground" style={MONO}>{ex.sets} series × {ex.reps} reps @ {ex.kg} kg</p>
              </div>
              <p className="text-xs font-bold text-muted-foreground" style={MONO}>{(ex.sets * ex.reps * ex.kg).toLocaleString()} kg</p>
            </div>
          ))}
        </div>

        <button
          onClick={onStart}
          className="w-full py-4 rounded-2xl font-black text-base active:scale-95 transition-all flex items-center justify-center gap-2 text-[#09090e]"
          style={{ background: routine.color }}
        >
          <Play size={18} fill="#09090e" /> Iniciar sesión
        </button>
        <div className="h-5" />
      </ScrollArea>
    </div>
  );
}

// ─── App root ─────────────────────────────────────────────────────────────────

export default function App() {
  const [screen, setScreen] = useState<Screen>("splash");
  const [tab, setTab] = useState<Tab>("home");
  const [selectedRoutine, setSelectedRoutine] = useState(ROUTINES[0]);
  const [selectedExercise, setSelectedExercise] = useState(EXERCISES[0]);

  const handleTabChange = (t: Tab) => {
    setTab(t);
    setScreen(t as Screen);
  };

  const go = (s: Screen) => setScreen(s);

  const showTabs = !["splash", "login", "register", "session-active", "session-summary"].includes(screen);

  const renderScreen = () => {
    switch (screen) {
      case "splash":
        return <Splash onDone={() => go("login")} />;
      case "login":
        return <Login onLogin={() => { go("home"); setTab("home"); }} onRegister={() => go("register")} />;
      case "register":
        return <Register onBack={() => go("login")} onDone={() => { go("home"); setTab("home"); }} />;
      case "home":
        return <HomeScreen onStartSession={() => { setSelectedRoutine(ROUTINES[0]); go("session-active"); }} onRank={() => go("rank")} />;
      case "routines":
        return <RoutinesScreen onStart={r => { setSelectedRoutine(r); go("session-active"); }} onDetail={r => { setSelectedRoutine(r); go("routine-detail"); }} />;
      case "exercises":
        return <ExercisesScreen onDetail={ex => { setSelectedExercise(ex); go("exercise-detail"); }} />;
      case "stats":
        return <StatsScreen />;
      case "coach":
        return <CoachScreen />;
      case "rank":
        return <RankScreen onBack={() => go("home")} />;
      case "exercise-detail":
        return <ExerciseDetail ex={selectedExercise} onBack={() => go("exercises")} />;
      case "routine-detail":
        return <RoutineDetail routine={selectedRoutine} onBack={() => go("routines")} onStart={() => go("session-active")} />;
      case "session-active":
        return <ActiveSession routine={selectedRoutine} onFinish={() => go("session-summary")} />;
      case "session-summary":
        return <SessionSummary routine={selectedRoutine} onDone={() => { go("home"); setTab("home"); }} />;
      default:
        return null;
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center py-10"
      style={{
        background: "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(200,241,53,0.06) 0%, transparent 60%), #050508",
        fontFamily: "'DM Sans', sans-serif",
      }}
    >
      <Phone>
        <div className="h-full flex flex-col" style={{ background: "#09090e", color: "#f0f0f5" }}>
          <div className="flex-1 min-h-0">
            {renderScreen()}
          </div>
          {showTabs && (
            <BottomTabs active={tab} onChange={t => { handleTabChange(t); }} />
          )}
        </div>
      </Phone>
    </div>
  );
}
