/* agents-px.js — pixel portraits for the 11 review agents.
 *
 * Each agent is a 14×16 pixel bust drawn to <canvas> with image-rendering: pixelated.
 * Palette chars:
 *   .  transparent
 *   K  ink outline       #15171C
 *   S  skin              #E2C49B
 *   s  skin shadow       #C29874
 *   H  hair              #2A2620   (overridable per char)
 *   h  hair highlight    #4A413A
 *   A  agent accent      (set per agent — their --a-* color)
 *   a  agent accent dark (derived darker shade)
 *   W  white highlight   #F4F5F7
 *   G  gray prop         #6B7280
 *   R  red prop          #8E3B36
 *   B  blue prop         #2A6573
 *   O  ochre prop        #8A6A24
 *   M  mouth             #7A4538
 *   F  glasses frame     #15171C  (alias of K but kept for clarity in maps)
 *   L  lens highlight    #DCE3EA
 *
 * Usage:
 *   <agent-px id="parser" size="48"></agent-px>
 *   <agent-px id="da" size="32" no-bg></agent-px>
 */

const BASE_PAL = {
  ".": null,
  "K": "#15171C",
  "S": "#E2C49B",
  "s": "#C29874",
  "H": "#2A2620",
  "h": "#4A413A",
  "W": "#F4F5F7",
  "G": "#6B7280",
  "R": "#8E3B36",
  "B": "#2A6573",
  "O": "#8A6A24",
  "M": "#7A4538",
  "F": "#15171C",
  "L": "#DCE3EA",
};

/* Per-agent accent (also exposed in CSS) and a derived dark shade.
   `a` is hand-tuned darker; `A` matches CSS --a-* token.
   `hair` overrides default hair color (optional). */
const AGENTS = {
  parser:    { name: "Parser",            zh: "文档解析员",   A: "#2D2F35", a: "#1B1D22" },
  checker:   { name: "Content Checker",   zh: "内容检查员",   A: "#2A6573", a: "#194851" },
  collector: { name: "Journal Collector", zh: "期刊收集员",   A: "#8A6A24", a: "#604918" },
  analyst:   { name: "Field Analyst",     zh: "领域分析员",   A: "#4F6B3F", a: "#384B2C" },
  se:        { name: "Senior Editor",     zh: "主编 SE",      A: "#7E3A48", a: "#582632" },
  ae:        { name: "Associate Editor",  zh: "责编 AE",      A: "#2F5840", a: "#1E3A2A" },
  r1:        { name: "Reviewer · Method", zh: "方法论审稿人", A: "#2E4173", a: "#1F2C50" },
  r2:        { name: "Reviewer · Domain", zh: "领域审稿人",   A: "#8A4A2E", a: "#5E311E" },
  r3:        { name: "Reviewer · Cross",  zh: "跨学科审稿人", A: "#6E5A2A", a: "#4A3B17" },
  da:        { name: "Devil's Advocate",  zh: "反方辩护人",   A: "#5A3B6E", a: "#3D264B" },
  final:     { name: "AE · Final",        zh: "终审编辑",     A: "#0E1014", a: "#000000" },
};

/* Each map is 14 wide × 16 tall. Read top-down.
   Distinct silhouettes via hair / hat / glasses / prop / collar.
   Last 6 rows are the bust — color via A/a/W. */

const MAPS = {

  /* PARSER — partings + reading glasses + small page in hand corner.
     Methodical, structural. */
  parser: [
    "..............",
    "....KKKKKK....",
    "...KHHHHHHK...",
    "..KHHWHWHHHK..",
    "..KHSSSSSSHK..",
    "..KFFKFFKFFK..",
    "..KSLKSLKSSK..",
    "..KSSSSSSSSK..",
    "..KsSSKMMSSsK.",
    "...KSSSSSSSK..",
    "....KKsssKK...",
    "...KAAKKAAK...",
    "..KAAAWAAAAK..",
    ".KAAAAWAAAAAK.",
    "KAAAAAWAAAAAAK",
    "KAAAAAAAAAAAAA",
  ],

  /* CONTENT CHECKER — green visor cap (editor visor) + plain collar.
     Reads as "fact-checker / copy editor". */
  checker: [
    "..............",
    "...KKKKKKKK...",
    "..KGGGGGGGGK..",
    "..KKKKKKKKKK..",
    "..KHSSSSSSHK..",
    "..KSKSSSSKSK..",
    "..KSSSSSSSSK..",
    "..KSSKMMSSSK..",
    "...KSSSSSSK...",
    "....KKKKK.....",
    "...KAAAAAK....",
    "..KAAWWWAAK...",
    ".KAAAWaaWAAK..",
    "KAAAAWWWAAAAK.",
    "KAAAAAAAAAAAAA",
    "..............",
  ],

  /* JOURNAL COLLECTOR — round glasses + tall book under arm.
     Older librarian energy. */
  collector: [
    "..............",
    "....KKKKKK....",
    "...KHHHHHHK...",
    "..KHhhHHHhhK..",
    "..KSSSSSSSSK..",
    "..KFKFKFKFKK..",
    "..KSLKSSKSLK..",
    "..KSSSSMMSSK..",
    "...KSSSSSSK...",
    "....KKKKK.....",
    "...KAAAAAK..KK",
    "..KAAOOOAAK.KO",
    ".KAAOWWWOAAKKO",
    "KAAAOWWWOAAAKO",
    "KAAAAOOOAAAAKK",
    "KAAAAAAAAAAAAA",
  ],

  /* FIELD ANALYST — short fringe, no glasses, bar-chart pin on chest. */
  analyst: [
    "..............",
    "...KKKKKKKK...",
    "..KHHHHHHHHK..",
    "..KHHHHHHHHK..",
    "..KSSSSSSSSK..",
    "..KSKSSSSKSK..",
    "..KSSSSSSSSK..",
    "..KSSSKMMSSK..",
    "...KSSSSSSK...",
    "....KKKKK.....",
    "...KAAAAAK....",
    "..KAAAaAAAK...",
    ".KAAAWAaAAAK..",
    "KAAAWWWAAAAAK.",
    "KAAAAAAAAAAAAA",
    "..............",
  ],

  /* SE — Senior Editor. Balding crown, bowtie, formal.
     Their accent is wine. */
  se: [
    "..............",
    "....HKKKKH....",
    "...KhHhHhHK...",
    "..KhHHHHHHhK..",
    "..KSSSSSSSSK..",
    "..KSKSSSSKSK..",
    "..KSSSSSSSSK..",
    "..KsSSKMMSSsK.",
    "...KSSSSSSK...",
    "....KKKKK.....",
    "..KKWAAAAWKK..",
    ".KAAWWAAWWAAK.",
    "KAAAAWWWWAAAAK",
    "KAAAAAAAAAAAAA",
    "KAAAAAAAAAAAAA",
    "..............",
  ],

  /* AE — Associate Editor. Mid hair part, clipboard outline visible. */
  ae: [
    "..............",
    "....KKKKKK....",
    "...KHHWHHWHK..",
    "..KHHHHHHHHK..",
    "..KSSSSSSSSK..",
    "..KSKSSSSKSK..",
    "..KSSSSSSSSK..",
    "..KSSKMMSSSK..",
    "...KSSSSSSK...",
    "....KKKKK..KKK",
    "...KAAAAAK.KWK",
    "..KAAWAAAAKKWK",
    ".KAAAWWAAAKKKK",
    "KAAAAWWAAAAAK.",
    "KAAAAAAAAAAAAA",
    "..............",
  ],

  /* R1 — Methodology reviewer. Rectangular glasses, lab-shirt collar. */
  r1: [
    "..............",
    "....KKKKKK....",
    "...KHHHHHHK...",
    "..KHHHHHHHHK..",
    "..KSSSSSSSSK..",
    "..FFFFFFFFFFK.",
    "..FLLFFFFLLFK.",
    "..FFFFKMMFFFK.",
    "...KSSSSSSK...",
    "....KKKKK.....",
    "...KAAAAAK....",
    "..KAAWWWAAK...",
    ".KAAAWWWAAAK..",
    "KAAAAWAAAAAAK.",
    "KAAAAAAAAAAAAA",
    "..............",
  ],

  /* R2 — Domain reviewer. Beard + thinker hand near chin. */
  r2: [
    "..............",
    "....KKKKKK....",
    "...KHHHHHHK...",
    "..KHHHHHHHHK..",
    "..KSSSSSSSSK..",
    "..KSKSSSSKSK..",
    "..KSSSSSSSSK..",
    "..KHHKMMHHHK..",
    "..KHHHHHHHHK..",
    "...KHHHHHK....",
    "..KKAAAAAKK...",
    ".KAAAaaaAAAK..",
    "KAAAaWWaAAAAK.",
    "KAAAAaaaAAAAA.",
    "KAAAAAAAAAAAAA",
    "..............",
  ],

  /* R3 — Cross-disciplinary reviewer. Short curly hair + open collar. */
  r3: [
    "..............",
    "...KHKHKHKHK..",
    "..KhHhHhHhHHK.",
    "..KHHhHHhHhHK.",
    "..KSSSSSSSSK..",
    "..KSKSSSSKSK..",
    "..KSSSSSSSSK..",
    "..KSSKMMSSSK..",
    "...KSSSSSSK...",
    "....KKKKK.....",
    "...KAAKKAAK...",
    "..KAAWaaWAAK..",
    ".KAAAWaaWAAAK.",
    "KAAAAaaaAAAAAK",
    "KAAAAAAAAAAAAA",
    "..............",
  ],

  /* DEVIL'S ADVOCATE — pulled-back hair, dark round glasses, red pocket
     square. Cooler stance. */
  da: [
    "..............",
    "....KHHHHK....",
    "...KHhHhhHK...",
    "..KHHHHHHHHK..",
    "..KSSSSSSSSK..",
    "..KFFFKFFFFK..",
    "..KFKFKFKFFK..",
    "..KSSSSMMSSK..",
    "..KSSSSSSSSK..",
    "...KKKKKK.....",
    "..KKAAAAAAKK..",
    ".KaaAARAaaAaK.",
    "KaAAAARAAAAaaK",
    "KaAAAAAAAAAaaK",
    "KaaAAAAAAAaaaK",
    "KKKKKKKKKKKKKK",
  ],

  /* AE FINAL — older AE, glasses on nose, severe black robe/jacket.
     The closer. */
  final: [
    "..............",
    "....HKKKKH....",
    "...KhHhHhhK...",
    "..KhHHHHHHhK..",
    "..KSSSSSSSSK..",
    "..KSKSSSSKSK..",
    "..KFLFFFFFLFK.",
    "..KSSSKMMSSSK.",
    "...KSSSSSSK...",
    "....KKKKK.....",
    "...KAAAAAK....",
    "..KAAWWWAAK...",
    ".KAAAWWWAAAK..",
    "KAAAAWWWAAAAK.",
    "KAAAAAAAAAAAAA",
    "KAAAAAAAAAAAAA",
  ],
};

/* Web component */
class AgentPx extends HTMLElement {
  static observedAttributes = ["id", "size", "no-bg", "scale"];

  connectedCallback() { this.render(); }
  attributeChangedCallback() { this.render(); }

  render() {
    const id = this.getAttribute("id") || "parser";
    const size = parseInt(this.getAttribute("size") || "48", 10);
    const noBg = this.hasAttribute("no-bg");
    const agent = AGENTS[id];
    const map = MAPS[id];
    if (!agent || !map) return;

    const W = 14, H = 16;
    // Build palette
    const pal = { ...BASE_PAL, A: agent.A, a: agent.a };
    // Off-screen canvas at native pixel resolution
    const c = document.createElement("canvas");
    c.width = W; c.height = H;
    const ctx = c.getContext("2d");
    for (let y = 0; y < H; y++) {
      const row = map[y] || "";
      for (let x = 0; x < W; x++) {
        const ch = row[x] || ".";
        const color = pal[ch];
        if (!color) continue;
        ctx.fillStyle = color;
        ctx.fillRect(x, y, 1, 1);
      }
    }

    // Scale up to requested size by drawing to a second canvas
    const scale = Math.max(1, Math.floor(size / W));
    const outW = W * scale, outH = H * scale;
    const out = document.createElement("canvas");
    out.width = outW; out.height = outH;
    const octx = out.getContext("2d");
    octx.imageSmoothingEnabled = false;
    octx.drawImage(c, 0, 0, outW, outH);

    this.innerHTML = "";
    this.style.display = "inline-flex";
    this.style.alignItems = "center";
    this.style.justifyContent = "center";
    this.style.boxSizing = "border-box";
    this.style.lineHeight = "0";
    this.style.verticalAlign = "middle";
    if (noBg) {
      this.style.background = "transparent";
      this.style.border = "0";
      this.style.padding = "0";
      this.style.width  = outW + "px";
      this.style.height = outH + "px";
    } else {
      this.style.background = `var(--a-${id}-tint, var(--bg-1))`;
      this.style.padding = "6px";
      this.style.borderRadius = "3px";
      this.style.border = "1px solid var(--line-1)";
      this.style.width  = (outW + 14) + "px";
      this.style.height = (outH + 14) + "px";
    }
    out.style.imageRendering = "pixelated";
    out.style.display = "block";
    this.appendChild(out);
  }
}
customElements.define("agent-px", AgentPx);

/* Export role metadata for use in HTML */
window.AGENTS = AGENTS;
