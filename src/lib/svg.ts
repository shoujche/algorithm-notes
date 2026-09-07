// 共享的 SVG 绘制工具与调色板（客户端使用）

export const C = {
  edge: '#B4B9CC',
  rev: '#E8663D',
  prev: '#2F9E7E',
  curr: '#E8663D',
  next: '#3F5BD6',
  nodeDefault: '#D7DAE6',
  ink: '#191B22',
  muted: '#8A8E99',
};

const SVGNS = 'http://www.w3.org/2000/svg';

export function el(tag: string, attrs: Record<string, string | number>): SVGElement {
  const e = document.createElementNS(SVGNS, tag);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  return e as SVGElement;
}

export function defsArrow(svg: SVGElement, id: string, color: string): void {
  const defs = el('defs', {});
  const m = el('marker', {
    id, markerWidth: 9, markerHeight: 9, refX: 7.5, refY: 3,
    orient: 'auto', markerUnits: 'strokeWidth',
  });
  m.appendChild(el('path', { d: 'M0,0 L8,3 L0,6 Z', fill: color }));
  defs.appendChild(m);
  svg.appendChild(defs);
}

export function drawNode(
  svg: SVGElement, x: number, y: number, val: number | string,
  opts: { stroke?: string; fill?: string } = {}
): void {
  const stroke = opts.stroke ?? C.nodeDefault;
  const fill = opts.fill ?? '#fff';
  const w = 66, h = 48;
  svg.appendChild(el('rect', {
    x, y, width: w, height: h, rx: 11, fill, stroke, 'stroke-width': 2,
    filter: 'drop-shadow(0 1px 2px rgba(25,27,34,.10))',
  }));
  const t = el('text', { x: x + w / 2, y: y + h / 2 + 6, 'text-anchor': 'middle', class: 'node-val' });
  t.textContent = String(val);
  svg.appendChild(t);
}
