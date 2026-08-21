import { useEffect, useMemo, useState } from "react";
import type { ButtonHTMLAttributes } from "react";
import type { LucideIcon } from "lucide-react";
import {
  AlarmClock,
  ArrowDownToLine,
  ArrowLeft,
  BarChart3,
  BedDouble,
  CalendarDays,
  Calculator,
  Check,
  ChevronDown,
  ClipboardList,
  Clock3,
  Download,
  FileSpreadsheet,
  FileText,
  Hotel,
  Mail,
  Menu,
  MoreHorizontal,
  Moon,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Sparkles,
  Trash2,
  UserRound,
  UsersRound,
  X,
} from "lucide-react";

type View = "dashboard" | "new" | "import" | "export" | "report" | "agenda" | "calculator";

type Reservation = {
  id: number;
  eta: string;
  name: string;
  qty: number;
  room: string;
  email: string;
  checkIn: string;
  checkOut: string;
  reservation: string;
  phone: string;
  information: string;
  ird: string;
  hsk: string;
  rate: string;
  trans: string;
};

const categoryStyles = {
  VIP: { color: "#00e5ff", soft: "rgba(0,229,255,.13)", label: "VIP" },
  BIRTHDAY: { color: "#ff5964", soft: "rgba(255,89,100,.13)", label: "Birthday" },
  HONEYMOON: { color: "#ffad42", soft: "rgba(255,173,66,.14)", label: "Honeymoon" },
  BABYMOON: { color: "#b99aff", soft: "rgba(185,154,255,.14)", label: "Babymoon" },
  ANNIVERSARY: { color: "#4ade80", soft: "rgba(74,222,128,.14)", label: "Anniversary" },
  RELAXURY: { color: "#f472b6", soft: "rgba(244,114,182,.14)", label: "Relaxury" },
  "TEAM MEMBER": { color: "#facc15", soft: "rgba(250,204,21,.14)", label: "Team member" },
} as const;

type Category = keyof typeof categoryStyles;

const quickLinks: Array<{ label: string; href: string; color: string }> = [
  {
    label: "ALICE",
    href: "https://auth.aliceapp.com/login-staff?__hstc=85647430.18528c557a8d4857356bbdc77be22153.1745273864718.1745273864718.1745273864718.1&__hssc=85647430.2.1745273864718&__hsfp=92250610",
    color: "#6555d9",
  },
  {
    label: "ARRIVALS",
    href: "https://hilton-my.sharepoint.com/shared?listurl=https%3A%2F%2Fhilton%2Dmy%2Esharepoint%2Ecom%2Fpersonal%2Fefrem%5Fcatellani%5Fwaldorfastoria%5Fcom%2FDocuments&e=5%3A5760d5a1b59d4b69adb09d888a758bb4&sharingv2=true&fromShare=true&at=9&CT=1782844742090&OR=OWA%2DNT%2DMail&SI=NonSentItems&clickParams=eyJYLUFwcE5hbWUiOiJNaWNyb3NvZnQgT3V0bG9vayBXZWIgQXBwIiwiWC1BcHBWZXJzaW9uIjoiMjAyNjA2MTkwMTAuMTIiLCJPUyI6IldpbmRvd3MgMTEifQ%3D%3D&cidOR=Client&id=%2Fpersonal%2Fefrem%5Fcatellani%5Fwaldorfastoria%5Fcom%2FDocuments%2FARRIVAL%20DAYS%2F2026&FolderCTID=0x0120000A5710A5FF38F342BA540726A6B97804",
    color: "#0877bb",
  },
  { label: "LA CENIA", href: "https://lacerniaadventures.com/", color: "#078f72" },
  { label: "NO LIMIT", href: "https://www.experiencecollectioncr.com/", color: "#d96639" },
  { label: "OPEN TABLE", href: "https://guestcenter.opentable.com/login", color: "#bd3138" },
  {
    label: "OUTLOOK-FW",
    href: "https://outlook.office365.com/mail/inbox/id/AAQkAGMyMWEwZDZkLTk2NDQtNDZiMC1hMmE1LWIxYjFmZGJjYjBmOAAQAIbRdEConWFGtPTirYcPWFY%3D",
    color: "#2384c8",
  },
  {
    label: "OUTLOOK-PC",
    href: "https://outlook.cloud.microsoft/mail/personalconcierge.costarica@waldorfastoria.com/",
    color: "#176eaf",
  },
  { label: "RELAXURY", href: "https://relaxury.agilesd.com/", color: "#c73377" },
  {
    label: "VTC",
    href: "https://hilton-my.sharepoint.com/shared?listurl=https%3A%2F%2Fhilton%2Dmy%2Esharepoint%2Ecom%2Fpersonal%2Fefrem%5Fcatellani%5Fwaldorfastoria%5Fcom%2FDocuments&e=5%3A8e5918d1d45b4d6b90289e3f445b4d82&sharingv2=true&fromShare=true&at=9&cidOR=SPO&id=%2Fpersonal%2Fefrem%5Fcatellani%5Fwaldorfastoria%5Fcom%2FDocuments%2FVIRTUAL%20SIGNATURES&FolderCTID=0x0120000A5710A5FF38F342BA540726A6B97804",
    color: "#bb7800",
  },
];

const initialReservations: Reservation[] = [
  { id: 101, eta: "2:00 PM", name: "Alexander Morgan", qty: 2, room: "1406", email: "alexander.morgan@email.com", checkIn: "June 19, 2026", checkOut: "June 23, 2026", reservation: "WA-82641", phone: "+1 305 555 0188", information: "VIP · Anniversary", ird: "Welcome amenity", hsk: "Pre-arrival", rate: "$1,250", trans: "SUV · 2 guests" },
  { id: 102, eta: "3:30 PM", name: "Sofia Bennett", qty: 2, room: "1202", email: "sofia.bennett@email.com", checkIn: "June 19, 2026", checkOut: "June 22, 2026", reservation: "WA-82654", phone: "+44 20 5555 0148", information: "HONEYMOON", ird: "Champagne", hsk: "Turn down", rate: "$980", trans: "Airport transfer" },
  { id: 103, eta: "5:00 PM", name: "Daniel Rivera", qty: 4, room: "1608", email: "daniel.rivera@email.com", checkIn: "June 20, 2026", checkOut: "June 27, 2026", reservation: "WA-82702", phone: "+1 212 555 0124", information: "Relaxury package", ird: "Beach setup", hsk: "Daily", rate: "$840", trans: "Private van" },
  { id: 104, eta: "1:00 PM", name: "Charlotte Wilson", qty: 2, room: "1104", email: "charlotte.wilson@email.com", checkIn: "June 20, 2026", checkOut: "June 25, 2026", reservation: "WA-82718", phone: "+33 1 55 55 0110", information: "BIRTHDAY", ird: "Cake · 6 PM", hsk: "Daily", rate: "$1,100", trans: "Sedan" },
  { id: 105, eta: "4:15 PM", name: "Michael Chen", qty: 1, room: "904", email: "michael.chen@email.com", checkIn: "June 21, 2026", checkOut: "June 24, 2026", reservation: "WA-82749", phone: "+1 415 555 0199", information: "TEAM MEMBER", ird: "Staff rate", hsk: "Standard", rate: "$520", trans: "None" },
  { id: 106, eta: "11:45 AM", name: "Emma Thompson", qty: 2, room: "1501", email: "emma.thompson@email.com", checkIn: "June 21, 2026", checkOut: "June 29, 2026", reservation: "WA-82751", phone: "+61 2 5550 0121", information: "BABYMOON", ird: "Mocktails", hsk: "Quiet room", rate: "$1,320", trans: "SUV · 2 guests" },
  { id: 107, eta: "6:00 PM", name: "Lucas Anderson", qty: 3, room: "1308", email: "lucas.anderson@email.com", checkIn: "June 22, 2026", checkOut: "June 26, 2026", reservation: "WA-82782", phone: "+1 617 555 0147", information: "VIP", ird: "Chef tasting", hsk: "Daily", rate: "$1,480", trans: "Private van" },
  { id: 108, eta: "2:45 PM", name: "Olivia Garcia", qty: 2, room: "1007", email: "olivia.garcia@email.com", checkIn: "June 22, 2026", checkOut: "June 24, 2026", reservation: "WA-82801", phone: "+34 91 555 0135", information: "ANNIVERSARY", ird: "Flowers", hsk: "Daily", rate: "$760", trans: "Sedan" },
];

const actionButtons: Array<{ label: string; view: View; icon: LucideIcon; className: string }> = [
  { label: "NUEVA", view: "new", icon: Plus, className: "bg-cyan-400 text-slate-950" },
  { label: "IMPORTAR", view: "import", icon: ArrowDownToLine, className: "bg-emerald-500 text-white" },
  { label: "EXPORTAR", view: "export", icon: Download, className: "bg-blue-500 text-white" },
  { label: "REPORTE", view: "report", icon: BarChart3, className: "bg-amber-500 text-slate-950" },
  { label: "AGENDA", view: "agenda", icon: CalendarDays, className: "bg-violet-500 text-white" },
  { label: "CALC", view: "calculator", icon: Calculator, className: "bg-rose-500 text-white" },
];

const keywordPattern = Object.keys(categoryStyles).sort((a, b) => b.length - a.length) as Category[];

function getCategory(value: string): Category | null {
  const upper = value.toUpperCase();
  return keywordPattern.find((keyword) => upper.includes(keyword)) ?? null;
}

function nightsBetween(checkIn: string, checkOut: string) {
  const start = new Date(checkIn);
  const end = new Date(checkOut);
  return Math.max(0, Math.round((end.getTime() - start.getTime()) / 86400000));
}

function formatDate(date: Date) {
  return new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" }).format(date);
}

function Button({ children, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" className={`inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-[11px] font-black tracking-[.04em] transition hover:-translate-y-px hover:brightness-110 active:translate-y-0 ${className}`} {...props}>
      {children}
    </button>
  );
}

function Header({ now }: { now: Date }) {
  return (
    <header className="flex items-center justify-between gap-6 border-b border-[#1b2a3a] pb-4">
      <div className="flex items-center gap-3">
        <div className="border-r border-[#806f32] pr-3 font-serif text-[32px] leading-none tracking-[.22em] text-[#d4af37]">WA</div>
        <div>
          <div className="text-[11px] font-extrabold tracking-[.18em] text-[#d4af37]">WALDORF ASTORIA</div>
          <div className="mt-1 text-[9px] font-semibold tracking-[.12em] text-slate-500">COSTA RICA · PUNTA CACIQUE</div>
          <div className="mt-1 text-sm font-extrabold text-cyan-300">Concierge Master <span className="text-slate-500">v5.1</span></div>
        </div>
      </div>
      <div className="text-right" aria-label="Hora local del sistema">
        <div className="flex items-center justify-end gap-2 text-xl font-black tracking-[.05em] text-cyan-300 drop-shadow-[0_0_12px_rgba(0,229,255,.5)]">
          <Clock3 size={18} strokeWidth={2.5} />
          {now.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" })}
        </div>
        <div className="mt-1 text-sm font-bold capitalize tracking-[.03em] text-cyan-300">{formatDate(now)}</div>
        <div className="mt-1 text-[9px] font-bold uppercase tracking-[.16em] text-slate-500">Local system time</div>
      </div>
    </header>
  );
}

function StatCard({ label, value, accent, icon: Icon }: { label: string; value: string | number; accent: string; icon: LucideIcon }) {
  return (
    <div className="rounded-xl border border-[#1c3144] bg-[#0d1723] p-3 shadow-[0_10px_25px_rgba(0,0,0,.16)]">
      <div className="mb-2 flex items-center justify-between text-[10px] font-bold uppercase tracking-[.12em] text-slate-500">
        {label}<Icon size={15} style={{ color: accent }} />
      </div>
      <div className="text-2xl font-black" style={{ color: accent }}>{value}</div>
    </div>
  );
}

function CategoryBadge({ value }: { value: string }) {
  const category = getCategory(value);
  if (!category) return <span className="text-slate-400">{value || "—"}</span>;
  const style = categoryStyles[category];
  return <span className="inline-flex rounded-md px-2 py-1 text-[10px] font-extrabold uppercase tracking-[.04em]" style={{ color: style.color, background: style.soft }}>{value}</span>;
}

function ReservationTable({ reservations, selectedId, onSelect }: { reservations: Reservation[]; selectedId: number | null; onSelect: (reservation: Reservation) => void }) {
  const columns = ["ETA", "NAME", "QTY", "ROOM", "EMAIL", "CHECK IN", "CHECK OUT", "NIGHTS", "RESERVATION", "PHONE", "INFORMATION", "IRD", "HSK", "RATE", "TRANS"];
  return (
    <div className="overflow-hidden rounded-xl border border-[#1d3549] bg-[#0a111b] shadow-[0_18px_45px_rgba(0,0,0,.22)]">
      <div className="overflow-x-auto">
        <table className="min-w-[1450px] w-full border-collapse text-left">
          <thead className="bg-cyan-300 text-[10px] font-black tracking-[.06em] text-[#00151d]">
            <tr>{columns.map((column) => <th key={column} className="whitespace-nowrap px-3 py-3">{column}</th>)}</tr>
          </thead>
          <tbody>
            {reservations.map((reservation) => {
              const isSelected = selectedId === reservation.id;
              const category = getCategory(reservation.information);
              return (
                <tr
                  key={reservation.id}
                  onClick={() => onSelect(reservation)}
                  className={`cursor-pointer border-0 transition ${isSelected ? "bg-cyan-300 text-[#00151d]" : category === "VIP" ? "bg-[#191507] text-[#f6d670] hover:bg-[#2a210a]" : "text-slate-200 odd:bg-[#0d1723] hover:bg-[#132c3d]"}`}
                >
                  <td className="whitespace-nowrap px-3 py-3 text-[11px] font-semibold">{reservation.eta}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-[12px] font-extrabold">{reservation.name}</td>
                  <td className="px-3 py-3 text-[11px]">{reservation.qty}</td>
                  <td className="px-3 py-3 text-[11px] font-bold">{reservation.room}</td>
                  <td className="px-3 py-3 text-[11px] text-slate-400">{reservation.email}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-[11px]">{reservation.checkIn}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-[11px]">{reservation.checkOut}</td>
                  <td className="px-3 py-3 text-center text-[12px] font-black text-cyan-300">{nightsBetween(reservation.checkIn, reservation.checkOut)}</td>
                  <td className="px-3 py-3 text-[11px] font-bold">{reservation.reservation}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-[11px]">{reservation.phone}</td>
                  <td className="px-3 py-3"><CategoryBadge value={reservation.information} /></td>
                  <td className="px-3 py-3"><CategoryBadge value={reservation.ird} /></td>
                  <td className="px-3 py-3"><CategoryBadge value={reservation.hsk} /></td>
                  <td className="px-3 py-3 text-[11px] font-bold">{reservation.rate}</td>
                  <td className="px-3 py-3"><CategoryBadge value={reservation.trans} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!reservations.length && <div className="px-5 py-12 text-center text-sm text-slate-500">No hay reservaciones con los filtros actuales.</div>}
    </div>
  );
}

function QuickLinks() {
  const navigateSameTab = (url: string) => {
    window.location.assign(url);
  };

  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-9">
      {quickLinks.map((link) => (
        <button
          key={link.label}
          type="button"
          onClick={() => navigateSameTab(link.href)}
          className="rounded-lg px-2 py-2 text-center text-[10px] font-black tracking-[.04em] text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,.16),0_4px_10px_rgba(0,0,0,.2)] transition hover:-translate-y-px hover:brightness-110"
          style={{ backgroundColor: link.color }}
        >
          {link.label}
        </button>
      ))}
    </div>
  );
}

function ActionBar({ activeView, onView }: { activeView: View; onView: (view: View) => void }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
      {actionButtons.map(({ label, view, icon: Icon, className }) => (
        <Button key={view} onClick={() => onView(activeView === view ? "dashboard" : view)} className={`${className} ${activeView === view ? "ring-2 ring-white/80 ring-offset-2 ring-offset-[#080d14]" : ""}`}>
          <Icon size={14} strokeWidth={2.6} />{label}
        </Button>
      ))}
    </div>
  );
}

function EmptyView({ title, icon: Icon, onBack }: { title: string; icon: LucideIcon; onBack: () => void }) {
  return (
    <section className="mx-auto max-w-5xl rounded-2xl border border-[#1d3549] bg-[#0d1723] p-8 text-center">
      <div className="mx-auto mb-4 grid size-14 place-items-center rounded-2xl bg-cyan-300/10 text-cyan-300"><Icon size={28} /></div>
      <h2 className="text-2xl font-black text-white">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">Esta sección está lista para conectarse con tu flujo operativo.</p>
      <Button onClick={onBack} className="mt-6 bg-slate-700 text-white"><ArrowLeft size={14} /> Regresar a la tabla</Button>
    </section>
  );
}

function ReservationForm({ onBack, onSave }: { onBack: () => void; onSave: (reservation: Reservation) => void }) {
  const [name, setName] = useState("");
  const [room, setRoom] = useState("");
  const [checkIn, setCheckIn] = useState("2026-06-19");
  const [checkOut, setCheckOut] = useState("2026-06-20");
  const [information, setInformation] = useState("");
  return (
    <section className="rounded-2xl border border-[#1d3549] bg-[#0d1723] p-5">
      <div className="mb-5 flex items-center justify-between"><div><p className="text-[10px] font-black uppercase tracking-[.16em] text-cyan-300">Reservation desk</p><h2 className="mt-1 text-2xl font-black text-white">Nueva reservación</h2></div><Button onClick={onBack} className="bg-slate-700 text-white"><X size={14} /> Cerrar</Button></div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs font-bold text-slate-400">Nombre<input value={name} onChange={(event) => setName(event.target.value)} className="mt-2 w-full rounded-lg border border-[#284057] bg-[#101c2a] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300" placeholder="Nombre del huésped" /></label>
        <label className="text-xs font-bold text-slate-400">Habitación<input value={room} onChange={(event) => setRoom(event.target.value)} className="mt-2 w-full rounded-lg border border-[#284057] bg-[#101c2a] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300" placeholder="Ej. 1406" /></label>
        <label className="text-xs font-bold text-slate-400">Check-in<input type="date" value={checkIn} onChange={(event) => setCheckIn(event.target.value)} className="mt-2 w-full rounded-lg border border-[#284057] bg-[#101c2a] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300" /></label>
        <label className="text-xs font-bold text-slate-400">Check-out<input type="date" value={checkOut} onChange={(event) => setCheckOut(event.target.value)} className="mt-2 w-full rounded-lg border border-[#284057] bg-[#101c2a] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300" /></label>
        <label className="text-xs font-bold text-slate-400 sm:col-span-2 lg:col-span-4">Information<input value={information} onChange={(event) => setInformation(event.target.value)} className="mt-2 w-full rounded-lg border border-[#284057] bg-[#101c2a] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300" placeholder="VIP, Birthday, Honeymoon…" /></label>
      </div>
      <Button disabled={!name.trim() || !room.trim()} onClick={() => { onSave({ id: Date.now(), eta: "2:00 PM", name, qty: 1, room, email: "—", checkIn: new Date(`${checkIn}T12:00:00`).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }), checkOut: new Date(`${checkOut}T12:00:00`).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }), reservation: "NEW", phone: "—", information, ird: "—", hsk: "—", rate: "—", trans: "—" }); }} className="mt-6 bg-cyan-300 text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"><Check size={14} /> Guardar reservación</Button>
    </section>
  );
}

function Dashboard({ reservations, selectedId, setSelectedId, setView }: { reservations: Reservation[]; selectedId: number | null; setSelectedId: (id: number | null) => void; setView: (view: View) => void }) {
  const [search, setSearch] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const [checkoutFilter, setCheckoutFilter] = useState("");
  const filtered = useMemo(() => reservations.filter((reservation) => {
    const text = `${reservation.name} ${reservation.room} ${reservation.reservation} ${reservation.phone} ${reservation.information} ${reservation.ird} ${reservation.trans}`.toLowerCase();
    return (!search || text.includes(search.toLowerCase())) && (!dateFilter || reservation.checkIn === new Date(`${dateFilter}T12:00:00`).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })) && (!checkoutFilter || reservation.checkOut === checkoutFilter);
  }), [reservations, search, dateFilter, checkoutFilter]);
  const vipCount = filtered.filter((reservation) => getCategory(reservation.information) === "VIP").length;
  const relaxuryCount = filtered.filter((reservation) => getCategory(`${reservation.information} ${reservation.ird} ${reservation.trans}`) === "RELAXURY").length;
  const today = new Date("2026-06-19T12:00:00");
  const checkoutDays = Array.from({ length: 6 }, (_, index) => new Date(today.getTime() + index * 86400000));
  const selected = reservations.find((reservation) => reservation.id === selectedId);

  return (
    <>
      <div className="grid gap-3 md:grid-cols-4">
        <StatCard label="Total reservas" value={filtered.length} accent="#00e5ff" icon={ClipboardList} />
        <StatCard label="VIP arrivals" value={vipCount} accent="#d4af37" icon={Sparkles} />
        <StatCard label="Relaxury" value={relaxuryCount} accent="#f472b6" icon={BedDouble} />
        <StatCard label="Noches reservadas" value={filtered.reduce((sum, reservation) => sum + nightsBetween(reservation.checkIn, reservation.checkOut), 0)} accent="#a78bfa" icon={Moon} />
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-[190px_1fr]">
        <aside className="rounded-xl border border-[#1d3549] bg-[#0d1723] p-3">
          <div className="mb-3 flex items-center gap-2 text-[11px] font-black uppercase tracking-[.09em] text-white"><Hotel size={15} className="text-cyan-300" /> Checking out</div>
          <div className="grid grid-cols-2 gap-2">{checkoutDays.map((date) => { const formatted = date.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }); const count = reservations.filter((reservation) => reservation.checkOut === formatted).length; const active = checkoutFilter === formatted; return <button type="button" key={formatted} onClick={() => setCheckoutFilter(active ? "" : formatted)} className={`rounded-lg px-2 py-2 text-[10px] font-black transition ${active ? "bg-cyan-300 text-slate-950" : "bg-[#142638] text-slate-300 hover:bg-[#1c3b51]"}`}>{date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}<span className="ml-1 opacity-70">{count}</span></button>; })}</div>
          <Button onClick={() => { setCheckoutFilter(""); setDateFilter(""); setSearch(""); }} className="mt-3 w-full bg-slate-700 text-white"><RefreshCw size={13} /> Ver todas</Button>
          <label className="mt-4 block text-[10px] font-bold uppercase tracking-[.1em] text-slate-500">Check-in date<input type="date" value={dateFilter} onChange={(event) => setDateFilter(event.target.value)} className="mt-2 w-full rounded-lg border border-[#284057] bg-[#101c2a] px-2 py-2 text-xs text-white outline-none focus:border-cyan-300" /></label>
        </aside>
        <div className="rounded-xl border border-[#1d3549] bg-[#0d1723] p-3">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><div className="text-[11px] font-black uppercase tracking-[.12em] text-cyan-300">Guest categories</div><div className="mt-1 text-xs text-slate-500">Live view of the selected reservations</div></div><div className="flex items-center gap-2 rounded-full border border-cyan-300/40 bg-cyan-300/10 px-3 py-1 text-xs font-black text-cyan-300"><UsersRound size={13} /> {filtered.length} guests</div></div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{(Object.keys(categoryStyles) as Category[]).map((category) => { const count = filtered.filter((reservation) => getCategory(reservation.information) === category).length; const style = categoryStyles[category]; return <div key={category} className="rounded-lg px-3 py-2" style={{ background: style.soft }}><div className="flex justify-between text-[10px] font-black uppercase" style={{ color: style.color }}><span>{style.label}</span><span>{count}</span></div><div className="mt-2 h-1 rounded-full bg-black/20"><div className="h-1 rounded-full" style={{ width: `${filtered.length ? Math.max(5, count / filtered.length * 100) : 0}%`, background: style.color }} /></div></div>; })}</div>
        </div>
      </div>
      <div className="mt-3"><ActionBar activeView="dashboard" onView={setView} /></div>
      <div className="mt-2"><QuickLinks /></div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><div className="relative min-w-[260px] flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por nombre, teléfono, reserva o categoría…" className="w-full rounded-lg border border-[#284057] bg-[#101827] py-2.5 pl-9 pr-9 text-xs text-white outline-none placeholder:text-slate-600 focus:border-cyan-300" />{search && <button type="button" onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-cyan-300"><X size={14} /></button>}</div><div className="text-[11px] font-bold text-slate-500">{filtered.length} de {reservations.length} reservas</div></div>
      <div className="mt-3"><ReservationTable reservations={filtered} selectedId={selectedId} onSelect={(reservation) => setSelectedId(reservation.id)} /></div>
      {selected && <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-cyan-300 bg-[#062334] px-4 py-3"><div className="flex items-center gap-3"><div className="grid size-8 place-items-center rounded-full bg-cyan-300 text-slate-950"><UserRound size={15} /></div><div><div className="text-[10px] font-black uppercase tracking-[.1em] text-cyan-300">Reserva seleccionada</div><div className="text-sm font-black text-white">{selected.name} <span className="font-medium text-slate-400">· Room {selected.room}</span></div></div></div><div className="flex gap-2"><Button onClick={() => setView("new")} className="bg-amber-500 text-slate-950"><Pencil size={13} /> Editar</Button><Button onClick={() => setView("export")} className="bg-violet-500 text-white"><Mail size={13} /> Carta</Button><Button onClick={() => { setSelectedId(null); }} className="bg-slate-700 text-white"><X size={13} /> Cerrar</Button></div></div>}
    </>
  );
}

export default function Index() {
  const [now, setNow] = useState(() => new Date());
  const [view, setView] = useState<View>("dashboard");
  const [reservations, setReservations] = useState(initialReservations);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const viewContent = view === "dashboard" ? <Dashboard reservations={reservations} selectedId={selectedId} setSelectedId={setSelectedId} setView={setView} /> : view === "new" ? <ReservationForm onBack={() => setView("dashboard")} onSave={(reservation) => { setReservations((current) => [reservation, ...current]); setView("dashboard"); }} /> : view === "import" ? <EmptyView title="Importar reservaciones" icon={FileSpreadsheet} onBack={() => setView("dashboard")} /> : view === "export" ? <EmptyView title="Exportar reservaciones" icon={Download} onBack={() => setView("dashboard")} /> : view === "report" ? <EmptyView title="Reporte de ocupación" icon={BarChart3} onBack={() => setView("dashboard")} /> : view === "agenda" ? <EmptyView title="Agenda de reservaciones" icon={CalendarDays} onBack={() => setView("dashboard")} /> : <EmptyView title="Calculadora" icon={Calculator} onBack={() => setView("dashboard")} />;

  return (
    <main className="min-h-screen bg-[#080d14] px-3 py-4 text-white sm:px-5 lg:px-8">
      <div className="mx-auto max-w-[1800px]
">
        <Header now={now} />
        <div className="py-4">{view !== "dashboard" && <div className="mb-4"><ActionBar activeView={view} onView={setView} /><div className="mt-2"><QuickLinks /></div></div>}{viewContent}</div>
        <footer className="mt-5 flex items-center justify-between border-t border-[#182839] pt-3 text-[9px] font-bold uppercase tracking-[.13em] text-slate-600"><span>Concierge Master · Waldorf Astoria Costa Rica</span><span className="hidden sm:inline-flex items-center gap-1"><AlarmClock size={12} /> Local system time</span></footer>
      </div>
    </main>
  );
}
