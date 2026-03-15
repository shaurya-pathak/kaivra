"""Web preview exporter — generates a self-contained HTML file with a Canvas-based player."""

from __future__ import annotations

import json
import os
import tempfile
import webbrowser
from pathlib import Path

from dsa_anim.dsl.schema import DocumentSpec
from dsa_anim.scene_graph.builder import build_scene_graph
from dsa_anim.themes.base import ThemeSpec
from dsa_anim.themes.loader import resolve_theme


def export_web_preview(
    doc: DocumentSpec,
    *,
    theme: ThemeSpec | None = None,
    serve: bool = False,
    port: int = 8080,
) -> None:
    """Export an HTML preview and optionally serve it."""
    theme = theme or resolve_theme(doc.meta.theme)
    graph = build_scene_graph(doc, theme)

    # Serialize scene graph to JSON for the JS player
    scenes_data = []
    for scene in graph.scenes:
        nodes_data = []
        for node in scene.nodes:
            nodes_data.append(_serialize_node(node))

        timeline_data = []
        for kf in scene.timeline:
            timeline_data.append({
                "target_id": kf.target_id,
                "action": kf.action.value,
                "start_time": kf.start_time,
                "duration": kf.duration,
                "easing": kf.easing,
                "to_value": kf.to_value,
                "from_value": kf.from_value,
                "style": kf.style,
                "color": kf.color,
                "stagger": kf.stagger,
                "phases": kf.phases,
                "to_id": kf.to_id,
                "offset_x": kf.offset_x,
                "offset_y": kf.offset_y,
                "from_offset_x": kf.from_offset_x,
                "from_offset_y": kf.from_offset_y,
            })

        camera_kfs = []
        for ckf in scene.camera_keyframes:
            camera_kfs.append({
                "action": ckf.action,
                "start_time": ckf.start_time,
                "duration": ckf.duration,
                "easing": ckf.easing,
                "to_zoom": ckf.to_zoom,
                "focus_id": ckf.focus_id,
            })

        scenes_data.append({
            "id": scene.id,
            "duration": scene.duration,
            "showProgress": scene.show_progress,
            "nodes": nodes_data,
            "timeline": timeline_data,
            "camera_initial": {
                "zoom": scene.camera_initial.zoom,
                "center_x": scene.camera_initial.center_x,
                "center_y": scene.camera_initial.center_y,
            },
            "camera_keyframes": camera_kfs,
            "transition": {
                "type": scene.transition.type,
                "duration": scene.transition.duration,
            } if scene.transition else None,
            "narration": scene.narration,
        })

    graph_json = json.dumps({
        "width": graph.width,
        "height": graph.height,
        "fps": graph.fps,
        "theme": graph.theme_name,
        "totalDuration": graph.total_duration,
        "showNarration": graph.show_narration,
        "scenes": scenes_data,
    })

    # Theme data for the JS renderer
    theme_data = _serialize_theme(theme)
    theme_json = json.dumps(theme_data)

    html = _generate_html(graph_json, theme_json, theme_data)

    if serve:
        _serve_with_reload(html, port)
    else:
        # Write to temp file and open in browser
        tmpdir = tempfile.mkdtemp(prefix="dsa-anim-")
        path = os.path.join(tmpdir, "preview.html")
        with open(path, "w") as f:
            f.write(html)
        print(f"Preview saved to {path}")
        webbrowser.open(f"file://{path}")


def _serialize_theme(theme: ThemeSpec) -> dict:
    """Serialize a runtime theme for the web preview player."""
    return {
        "backgroundColor": theme.background_color,
        "textColor": theme.text_color,
        "textLight": theme.text_light,
        "accent": theme.accent,
        "success": theme.success,
        "muted": theme.muted,
        "boxFill": theme.box_fill,
        "boxBorder": theme.box_border,
        "boxBorderWidth": theme.box_border_width,
        "boxCornerRadius": theme.box_corner_radius,
        "boxPadding": theme.box_padding,
        "tokenFill": theme.token_fill,
        "tokenBorder": theme.token_border,
        "tokenCornerRadius": theme.token_corner_radius,
        "tokenBadgeFontSize": theme.token_badge_font_size,
        "tokenBadgeColor": theme.token_badge_color,
        "tokenBadgeOpacity": theme.token_badge_opacity,
        "tokenBadgeOffsetY": theme.token_badge_offset_y,
        "connectorColor": theme.connector_color,
        "connectorWidth": theme.connector_width,
        "arrowSize": theme.arrow_size,
        "displayFontCss": theme.font_stack_for_css("display"),
        "bodyFontCss": theme.font_stack_for_css("body"),
        "codeFontCss": theme.font_stack_for_css("code"),
        "fontSizeDisplay": theme.font_size_display,
        "fontSizeHeading": theme.font_size_heading,
        "fontSizeSectionHeading": theme.font_size_section_heading,
        "fontSizeBody": theme.font_size_body,
        "fontSizeCaption": theme.font_size_caption,
        "fontSizeCode": theme.font_size_code,
        "narrationBackgroundColor": theme.narration_background_color,
        "narrationTextColor": theme.narration_text_color,
        "narrationFontSize": theme.narration_font_size,
        "narrationBarHeight": theme.narration_bar_height,
        "narrationBottomOffset": theme.narration_bottom_offset,
        "narrationHorizontalPadding": theme.narration_horizontal_padding,
        "narrationLineHeight": theme.narration_line_height,
        "calloutBackgroundColor": theme.callout_background_color,
        "calloutTextColor": theme.callout_text_color,
        "calloutBorderColor": theme.callout_border_color,
        "calloutBorderWidth": theme.callout_border_width,
        "calloutCornerRadius": theme.callout_corner_radius,
        "calloutPadding": theme.callout_padding,
        "calloutFontSize": theme.callout_font_size,
        "calloutMaxWidth": theme.callout_max_width,
        "calloutLineHeight": theme.callout_line_height,
        "calloutPointerColor": theme.callout_pointer_color,
        "calloutPointerWidth": theme.callout_pointer_width,
        "calloutPointerDash": list(theme.callout_pointer_dash),
        "progressBarColor": theme.progress_bar_color,
        "progressBarHeight": theme.progress_bar_height,
        "progressBarOpacity": theme.progress_bar_opacity,
        "previewPageBackground": theme.preview_page_background,
        "previewControlsTextColor": theme.preview_controls_text_color,
        "previewCanvasCornerRadius": theme.preview_canvas_corner_radius,
        "previewCanvasShadow": theme.preview_canvas_shadow,
        "previewButtonFill": theme.preview_button_fill,
        "previewButtonHoverFill": theme.preview_button_hover_fill,
        "previewButtonTextColor": theme.preview_button_text_color,
        "previewButtonCornerRadius": theme.preview_button_corner_radius,
        "previewButtonFontSize": theme.preview_button_font_size,
        "previewTimelineAccent": theme.preview_timeline_accent,
        "previewNarrationTextColor": theme.preview_narration_text_color,
    }


def _serialize_node(node) -> dict:
    """Serialize a SceneNode to JSON-compatible dict."""
    data = {
        "id": node.id,
        "type": node.obj_type.value,
        "rect": {"x": node.rect.x, "y": node.rect.y, "w": node.rect.width, "h": node.rect.height},
        "content": node.content,
        "style": node.style,
        "stylePops": node.style_props,
        "persistent": node.persistent,
        "label": node.label,
        "tokenId": node.token_id,
        "fromId": node.from_id,
        "toId": node.to_id,
        "idlePreset": node.idle_preset,
        "idleIntensity": node.idle_intensity,
        "idleSpeed": node.idle_speed,
        "idleAxis": node.idle_axis,
        "defaultVisible": node.default_visible,
        "scaleText": node.scale_text,
        "baseScaleX": node.base_scale_x,
        "baseScaleY": node.base_scale_y,
        "layoutRole": node.layout_role,
        "children": [_serialize_node(c) for c in node.children],
    }
    return data


def _generate_html(graph_json: str, theme_json: str, theme_data: dict) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>dsa-anim Preview</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: {theme_data["previewPageBackground"]}; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; font-family: {theme_data["bodyFontCss"]}; }}
  #container {{ position: relative; }}
  canvas {{ border-radius: {theme_data["previewCanvasCornerRadius"]}px; box-shadow: {theme_data["previewCanvasShadow"]}; }}
  #controls {{ display: flex; align-items: center; gap: 12px; margin-top: 16px; color: {theme_data["previewControlsTextColor"]}; }}
  button {{ background: {theme_data["previewButtonFill"]}; color: {theme_data["previewButtonTextColor"]}; border: none; padding: 8px 20px; border-radius: {theme_data["previewButtonCornerRadius"]}px; cursor: pointer; font-size: {theme_data["previewButtonFontSize"]}px; font-family: {theme_data["bodyFontCss"]}; }}
  button:hover {{ background: {theme_data["previewButtonHoverFill"]}; }}
  #timeline {{ width: 400px; accent-color: {theme_data["previewTimelineAccent"]}; }}
  #time {{ font-variant-numeric: tabular-nums; min-width: 100px; text-align: center; }}
  #narration {{ color: {theme_data["previewNarrationTextColor"]}; margin-top: 8px; font-style: italic; max-width: 600px; text-align: center; }}
</style>
</head>
<body>
<div id="container">
  <canvas id="canvas"></canvas>
</div>
<div id="controls">
  <button id="playBtn">Play</button>
  <input type="range" id="timeline" min="0" max="1000" value="0">
  <span id="time">0:00 / 0:00</span>
</div>
<div id="narration"></div>
<script>
const GRAPH = {graph_json};
const THEME = {theme_json};

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
canvas.width = GRAPH.width;
canvas.height = GRAPH.height;
// Scale canvas for display
const maxW = Math.min(window.innerWidth - 40, 1200);
const scale = maxW / GRAPH.width;
canvas.style.width = (GRAPH.width * scale) + 'px';
canvas.style.height = (GRAPH.height * scale) + 'px';

let playing = false;
let currentTime = 0;
let sceneTime = 0;
let lastTimestamp = null;

const playBtn = document.getElementById('playBtn');
const timelineSlider = document.getElementById('timeline');
const timeDisplay = document.getElementById('time');
const narrationDiv = document.getElementById('narration');

playBtn.addEventListener('click', () => {{
  playing = !playing;
  playBtn.textContent = playing ? 'Pause' : 'Play';
  if (playing) lastTimestamp = performance.now();
}});

timelineSlider.addEventListener('input', () => {{
  currentTime = (timelineSlider.value / 1000) * GRAPH.totalDuration;
  render(currentTime);
}});

function formatTime(s) {{
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return m + ':' + String(sec).padStart(2, '0');
}}

// Easing functions
const easings = {{
  'linear': t => t,
  'ease-in': t => t * t,
  'ease-out': t => 1 - (1 - t) * (1 - t),
  'ease-in-out': t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2,
  'spring': t => {{ const c4 = (2 * Math.PI) / 3; return t <= 0 ? 0 : t >= 1 ? 1 : -(Math.pow(2, 10 * t - 10)) * Math.sin((t * 10 - 10.75) * c4) + 1; }},
  'bounce': t => {{ const n1 = 7.5625, d1 = 2.75; if (t < 1/d1) return n1*t*t; if (t < 2/d1) {{ t -= 1.5/d1; return n1*t*t+0.75; }} if (t < 2.5/d1) {{ t -= 2.25/d1; return n1*t*t+0.9375; }} t -= 2.625/d1; return n1*t*t+0.984375; }},
}};

function getEasing(name) {{ return easings[name] || easings['ease-in-out']; }}

function getSceneAtTime(t) {{
  let elapsed = 0;
  for (const scene of GRAPH.scenes) {{
    if (t < elapsed + scene.duration) return {{ scene, localTime: t - elapsed }};
    elapsed += scene.duration;
  }}
  return {{ scene: null, localTime: 0 }};
}}

function getProgress(kf, t) {{
  if (t < kf.start_time) return null;
  if (kf.duration <= 0) return t >= kf.start_time ? 1 : null;
  const raw = (t - kf.start_time) / kf.duration;
  if (raw > 1) return null;
  return getEasing(kf.easing)(Math.max(0, Math.min(1, raw)));
}}

function applyAnimations(nodeMap, keyframes, t) {{
  for (const id in nodeMap) {{
    if (nodeMap[id].persistent) {{
      nodeMap[id]._visible = true;
      nodeMap[id]._opacity = 1;
      nodeMap[id]._drawProgress = 1;
    }} else if (nodeMap[id].defaultVisible) {{
      nodeMap[id]._visible = true;
      nodeMap[id]._opacity = 1;
      nodeMap[id]._drawProgress = 1;
    }} else {{
      nodeMap[id]._visible = false;
      nodeMap[id]._opacity = 0;
      nodeMap[id]._drawProgress = 0;
    }}
    nodeMap[id]._scaleX = nodeMap[id].baseScaleX || 1;
    nodeMap[id]._scaleY = nodeMap[id].baseScaleY || 1;
    nodeMap[id]._translateX = 0;
    nodeMap[id]._translateY = 0;
    nodeMap[id]._highlightIntensity = 0;
  }}
  for (const kf of keyframes) {{
    const node = nodeMap[kf.target_id];
    if (!node) continue;
    const p = getProgress(kf, t);
    const done = t >= kf.start_time + kf.duration;

    switch(kf.action) {{
      case 'appear':
        if (t >= kf.start_time) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; }}
        break;
      case 'disappear':
        if (t < kf.start_time) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; }}
        else {{ node._visible = false; node._opacity = 0; }}
        break;
      case 'fade-in':
        if (p !== null) {{ node._visible = true; node._opacity = Math.max(node._opacity, p); node._drawProgress = 1; }}
        else if (done) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; }}
        break;
      case 'fade-out':
        if (p !== null) {{ node._visible = true; node._opacity = 1 - p; node._drawProgress = 1; }}
        else if (done) {{ node._visible = false; node._opacity = 0; }}
        break;
      case 'type': case 'draw':
        if (p !== null) {{ node._visible = true; node._opacity = 1; node._drawProgress = p; }}
        else if (done) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; }}
        break;
      case 'scale':
        const to = (kf.to_value !== undefined && kf.to_value !== null) ? kf.to_value : 1;
        const from = (kf.from_value !== undefined && kf.from_value !== null) ? kf.from_value : 1;
        if (p !== null) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; const s = from + (to - from) * p; node._scaleX = s; node._scaleY = s; }}
        else if (done) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; node._scaleX = to; node._scaleY = to; }}
        break;
      case 'move': {{
        const mdx = kf.offset_x || 0, mdy = kf.offset_y || 0;
        const fdx = (kf.from_offset_x !== undefined && kf.from_offset_x !== null) ? kf.from_offset_x : 0;
        const fdy = (kf.from_offset_y !== undefined && kf.from_offset_y !== null) ? kf.from_offset_y : 0;
        if (p !== null) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; node._translateX = fdx + (mdx - fdx) * p; node._translateY = fdy + (mdy - fdy) * p; }}
        else if (done) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; node._translateX = mdx; node._translateY = mdy; }}
        break;
      }}
      case 'move-to':
        const tnode = kf.to_id ? nodeMap[kf.to_id] : null;
        const dx = tnode ? (tnode.rect.x + tnode.rect.w/2 - (node.rect.x + node.rect.w/2)) + (kf.offset_x || 0) : (kf.offset_x || 0);
        const dy = tnode ? (tnode.rect.y + tnode.rect.h/2 - (node.rect.y + node.rect.h/2)) + (kf.offset_y || 0) : (kf.offset_y || 0);
        if (p !== null) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; node._translateX = dx * p; node._translateY = dy * p; }}
        else if (done) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; node._translateX = dx; node._translateY = dy; }}
        break;
      case 'highlight': case 'pulse':
        if (p !== null) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; node._highlightIntensity = p; }}
        else if (done) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; }}
        break;
      case 'build':
        if (kf.phases) {{
          for (const phase of kf.phases) {{
            const ps = parseFloat(phase.at);
            const pd = parseFloat(phase.duration);
            if (t >= ps) {{ node._visible = true; node._opacity = 1; node._drawProgress = pd > 0 ? Math.min(1, (t - ps) / pd) : 1; }}
          }}
        }}
        break;
      default:
        if (p !== null) {{ node._visible = true; node._opacity = p; node._drawProgress = p; }}
        else if (done) {{ node._visible = true; node._opacity = 1; node._drawProgress = 1; }}
    }}
  }}
}}

function hexToRgba(hex, alpha) {{
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  const baseAlpha = h.length >= 8 ? parseInt(h.substring(6, 8), 16) / 255 : 1;
  const finalAlpha = (alpha !== undefined ? alpha : 1) * baseAlpha;
  return `rgba(${{r}},${{g}},${{b}},${{finalAlpha}})`;
}}

function fontSpec(weight, size, family) {{
  return `${{weight}} ${{size}}px ${{family}}`;
}}

function roundedRect(ctx, x, y, w, h, r) {{
  r = Math.min(r, w/2, h/2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}}

function drawNode(ctx, node, nodeMap) {{
  if (!node._visible) return;
  ctx.save();
  ctx.globalAlpha = node._opacity;

  const r = node.rect;
  let idleDx = 0, idleDy = 0, idleScale = 1;
  if (node.idlePreset) {{
    const preset = node.idlePreset;
    const speed = node.idleSpeed || 1.5;
    const intensity = (node.idleIntensity !== undefined && node.idleIntensity !== null)
      ? node.idleIntensity
      : (preset === 'breathe' ? 0.03 : 6);
    if (preset === 'float' || preset === 'jitter') {{
      const freq = preset === 'jitter' ? speed * 3.0 : speed;
      const axis = node.idleAxis || 'both';
      if (axis === 'x' || axis === 'both') idleDx = Math.sin(sceneTime * freq) * intensity;
      if (axis === 'y' || axis === 'both') idleDy = Math.cos(sceneTime * freq * 1.3) * intensity;
    }}
    if (preset === 'breathe') {{
      idleScale = 1 + Math.sin(sceneTime * speed) * intensity;
    }}
  }}

  const tx = (node._translateX || 0) + idleDx;
  const ty = (node._translateY || 0) + idleDy;
  if (tx || ty) {{
    ctx.translate(tx, ty);
  }}
  const sx = (node._scaleX || 1) * idleScale;
  const sy = (node._scaleY || 1) * idleScale;
  const shellOnlyScale = (node.scaleText === false) && (node.type === 'box' || node.type === 'token');
  if (shellOnlyScale && (sx !== 1 || sy !== 1)) {{
    ctx.save();
    const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
    ctx.translate(cx, cy);
    ctx.scale(sx, sy);
    ctx.translate(-cx, -cy);
    drawNodeShell(ctx, node, nodeMap);
    ctx.restore();
    drawNodeTextLayer(ctx, node);
    ctx.restore();
    return;
  }}
  if (sx !== 1 || sy !== 1) {{
    const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
    ctx.translate(cx, cy);
    ctx.scale(sx, sy);
    ctx.translate(-cx, -cy);
  }}

  drawNodeVisual(ctx, node, nodeMap);

  ctx.restore();
}}

function drawNodeVisual(ctx, node, nodeMap) {{
  switch(node.type) {{
    case 'text': drawText(ctx, node); break;
    case 'box': drawBox(ctx, node); break;
    case 'token': drawToken(ctx, node); break;
    case 'connector': drawConnector(ctx, node, nodeMap); break;
    case 'group': drawGroup(ctx, node, nodeMap); break;
    case 'circle': drawCircle(ctx, node); break;
    case 'callout': drawCallout(ctx, node, nodeMap); break;
    default: drawBox(ctx, node); break;
  }}
}}

function drawNodeShell(ctx, node, nodeMap) {{
  switch(node.type) {{
    case 'box': drawBoxShell(ctx, node); break;
    case 'token': drawTokenShell(ctx, node); break;
    default: drawNodeVisual(ctx, node, nodeMap); break;
  }}
}}

function drawNodeTextLayer(ctx, node) {{
  switch(node.type) {{
    case 'box': drawBoxText(ctx, node); break;
    case 'token': drawTokenText(ctx, node); break;
  }}
}}

function drawText(ctx, node) {{
  if (!node.content) return;
  const sp = node.stylePops || {{}};
  const fontSize = sp.font_size || THEME.fontSizeBody;
  const color = sp.color || THEME.textColor;
  const weight = sp.font_weight === 'bold' ? 'bold' : 'normal';
  const family = sp.font_css || THEME.bodyFontCss;
  ctx.font = fontSpec(weight, fontSize, family);
  ctx.fillStyle = hexToRgba(color, node._opacity);
  let text = node.content;
  if (node._drawProgress < 1) text = text.substring(0, Math.floor(text.length * node._drawProgress));
  const m = ctx.measureText(text);
  ctx.fillText(text, node.rect.x + (node.rect.w - m.width) / 2, node.rect.y + node.rect.h / 2 + fontSize * 0.35);
}}

function drawBox(ctx, node) {{
  drawBoxShell(ctx, node);
  drawBoxText(ctx, node);
}}

function drawBoxShell(ctx, node) {{
  const r = node.rect;
  roundedRect(ctx, r.x, r.y, r.w, r.h, THEME.boxCornerRadius);
  ctx.fillStyle = hexToRgba(THEME.boxFill, node._opacity);
  ctx.fill();
  ctx.strokeStyle = hexToRgba(THEME.boxBorder, node._opacity);
  ctx.lineWidth = THEME.boxBorderWidth;
  ctx.stroke();
}}

function drawBoxText(ctx, node) {{
  const r = node.rect;
  if (node.content) {{
    ctx.font = fontSpec('normal', THEME.fontSizeBody, THEME.bodyFontCss);
    ctx.fillStyle = hexToRgba(THEME.textColor, node._opacity);
    let text = node.content;
    if (node._drawProgress < 1) text = text.substring(0, Math.floor(text.length * node._drawProgress));
    const m = ctx.measureText(text);
    ctx.fillText(text, r.x + (r.w - m.width) / 2, r.y + r.h / 2 + THEME.fontSizeBody * 0.35);
  }}
}}

function drawToken(ctx, node) {{
  drawTokenShell(ctx, node);
  drawTokenText(ctx, node);
}}

function drawTokenShell(ctx, node) {{
  const r = node.rect;
  roundedRect(ctx, r.x, r.y, r.w, r.h, THEME.tokenCornerRadius);
  ctx.fillStyle = hexToRgba(THEME.tokenFill, node._opacity);
  ctx.fill();
  ctx.strokeStyle = hexToRgba(THEME.tokenBorder, node._opacity);
  ctx.lineWidth = THEME.boxBorderWidth;
  ctx.stroke();
}}

function drawTokenText(ctx, node) {{
  const r = node.rect;
  if (node.content) {{
    ctx.font = fontSpec('normal', THEME.fontSizeBody, THEME.bodyFontCss);
    ctx.fillStyle = hexToRgba(THEME.textColor, node._opacity);
    const text = node.content.trim();
    const m = ctx.measureText(text);
    ctx.fillText(text, r.x + (r.w - m.width) / 2, r.y + r.h / 2 + THEME.fontSizeBody * 0.35);
  }}
  if (node.tokenId != null) {{
    ctx.font = fontSpec('normal', THEME.tokenBadgeFontSize, THEME.bodyFontCss);
    ctx.fillStyle = hexToRgba(THEME.tokenBadgeColor, node._opacity * THEME.tokenBadgeOpacity);
    const tid = String(node.tokenId);
    const m = ctx.measureText(tid);
    ctx.fillText(tid, r.x + (r.w - m.width) / 2, r.y + r.h + THEME.tokenBadgeOffsetY);
  }}
}}

function drawConnector(ctx, node, nodeMap) {{
  if (!node.fromId || !node.toId) return;
  const from = nodeMap[node.fromId], to = nodeMap[node.toId];
  if (!from || !to) return;
  const sx = from.rect.x + from.rect.w, sy = from.rect.y + from.rect.h / 2;
  const ex = to.rect.x, ey = to.rect.y + to.rect.h / 2;
  ctx.strokeStyle = hexToRgba(THEME.connectorColor, node._opacity);
  ctx.lineWidth = THEME.connectorWidth;
  ctx.beginPath();
  ctx.moveTo(sx, sy);
  const endX = sx + (ex - sx) * node._drawProgress;
  const endY = sy + (ey - sy) * node._drawProgress;
  ctx.lineTo(endX, endY);
  ctx.stroke();
}}

function drawGroup(ctx, node, nodeMap) {{
  if (node.label) {{
    ctx.font = fontSpec('bold', THEME.fontSizeCaption, THEME.bodyFontCss);
    ctx.fillStyle = hexToRgba(THEME.textLight, node._opacity);
    const m = ctx.measureText(node.label);
    ctx.fillText(node.label, node.rect.x + (node.rect.w - m.width) / 2, node.rect.y - 8);
  }}
  for (const child of (node.children || [])) {{
    const prevVisible = child._visible;
    const prevOpacity = child._opacity;
    const prevDrawProgress = child._drawProgress;
    child._visible = node._visible && prevVisible;
    child._opacity = node._opacity * prevOpacity;
    child._drawProgress = node._drawProgress * prevDrawProgress;
    drawNode(ctx, child, nodeMap);
    child._visible = prevVisible;
    child._opacity = prevOpacity;
    child._drawProgress = prevDrawProgress;
  }}
}}

function drawCircle(ctx, node) {{
  const cx = node.rect.x + node.rect.w / 2;
  const cy = node.rect.y + node.rect.h / 2;
  const radius = Math.min(node.rect.w, node.rect.h) / 2;
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.fillStyle = hexToRgba(THEME.boxFill, node._opacity);
  ctx.fill();
  ctx.strokeStyle = hexToRgba(THEME.boxBorder, node._opacity);
  ctx.lineWidth = THEME.boxBorderWidth;
  ctx.stroke();
  if (node.content) {{
    ctx.font = fontSpec('normal', THEME.fontSizeBody, THEME.bodyFontCss);
    ctx.fillStyle = hexToRgba(THEME.textColor, node._opacity);
    const m = ctx.measureText(node.content);
    ctx.fillText(node.content, cx - m.width / 2, cy + THEME.fontSizeBody * 0.35);
  }}
}}

function drawCallout(ctx, node, nodeMap) {{
  if (!node.content) return;
  const r = node.rect;
  const padding = THEME.calloutPadding;
  ctx.font = fontSpec('normal', THEME.calloutFontSize, THEME.bodyFontCss);

  const words = node.content.split(/\\s+/);
  const lines = [];
  let current = '';
  for (const word of words) {{
    const test = (current + ' ' + word).trim();
    if (ctx.measureText(test).width > THEME.calloutMaxWidth && current) {{
      lines.push(current);
      current = word;
    }} else {{
      current = test;
    }}
  }}
  if (current) lines.push(current);

  const bubbleW = Math.min(THEME.calloutMaxWidth + padding * 2, r.w);
  const bubbleH = lines.length * THEME.calloutLineHeight + padding * 2;
  const bx = r.x + (r.w - bubbleW) / 2;
  const by = r.y + (r.h - bubbleH) / 2;

  roundedRect(ctx, bx, by, bubbleW, bubbleH, THEME.calloutCornerRadius);
  ctx.fillStyle = hexToRgba(THEME.calloutBackgroundColor, node._opacity);
  ctx.fill();
  ctx.strokeStyle = hexToRgba(THEME.calloutBorderColor, node._opacity);
  ctx.lineWidth = THEME.calloutBorderWidth;
  ctx.stroke();

  ctx.fillStyle = hexToRgba(THEME.calloutTextColor, node._opacity);
  for (let i = 0; i < lines.length; i++) {{
    const m = ctx.measureText(lines[i]);
    ctx.fillText(lines[i], bx + (bubbleW - m.width) / 2, by + padding + THEME.calloutFontSize + i * THEME.calloutLineHeight);
  }}

  if (node.fromId) {{
    const target = nodeMap[node.fromId];
    if (target) {{
      ctx.beginPath();
      ctx.setLineDash(THEME.calloutPointerDash);
      ctx.strokeStyle = hexToRgba(THEME.calloutPointerColor, node._opacity);
      ctx.lineWidth = THEME.calloutPointerWidth;
      ctx.moveTo(bx + bubbleW / 2, by + bubbleH);
      ctx.lineTo(target.rect.x + target.rect.w / 2, target.rect.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }}
  }}
}}

function render(t) {{
  const {{ scene, localTime }} = getSceneAtTime(t);
  sceneTime = localTime;
  ctx.clearRect(0, 0, GRAPH.width, GRAPH.height);

  // Background
  ctx.fillStyle = THEME.backgroundColor;
  ctx.fillRect(0, 0, GRAPH.width, GRAPH.height);

  if (!scene) return;

  // Build node map
  const nodeMap = {{}};
  function mapNodes(nodes) {{
    for (const n of nodes) {{
      nodeMap[n.id] = n;
      if (n.children) mapNodes(n.children);
    }}
  }}
  mapNodes(scene.nodes);

  applyAnimations(nodeMap, scene.timeline, localTime);

  // Camera
  ctx.save();
  let zoom = scene.camera_initial.zoom || 1;
  let centerX = scene.camera_initial.center_x || (GRAPH.width / 2);
  let centerY = scene.camera_initial.center_y || (GRAPH.height / 2);

  function focusPoint(focusId) {{
    if (!focusId || focusId === 'center') return [GRAPH.width / 2, GRAPH.height / 2];
    const n = nodeMap[focusId];
    if (!n) return [GRAPH.width / 2, GRAPH.height / 2];
    return [n.rect.x + n.rect.w / 2, n.rect.y + n.rect.h / 2];
  }}

  for (const ckf of scene.camera_keyframes) {{
    if (localTime < ckf.start_time) continue;
    const raw = ckf.duration > 0 ? Math.min(1, (localTime - ckf.start_time) / ckf.duration) : 1;
    const p = getEasing(ckf.easing)(raw);
    const [tx, ty] = focusPoint(ckf.focus_id);

    if (ckf.action === 'pan') {{
      centerX = centerX + (tx - centerX) * p;
      centerY = centerY + (ty - centerY) * p;
    }}
    if (ckf.action === 'zoom' && ckf.to_zoom != null) {{
      zoom = zoom + (ckf.to_zoom - zoom) * p;
      if (ckf.focus_id) {{
        centerX = centerX + (tx - centerX) * p;
        centerY = centerY + (ty - centerY) * p;
      }}
    }}
  }}

  if (zoom !== 1 || centerX !== GRAPH.width / 2 || centerY !== GRAPH.height / 2) {{
    ctx.translate(centerX, centerY);
    ctx.scale(zoom, zoom);
    ctx.translate(-centerX, -centerY);
  }}

  for (const node of scene.nodes) drawNode(ctx, node, nodeMap);
  ctx.restore();

  if (scene.showProgress && scene.duration > 0) {{
    const progress = localTime / scene.duration;
    ctx.fillStyle = hexToRgba(THEME.progressBarColor, THEME.progressBarOpacity);
    ctx.fillRect(0, 0, GRAPH.width * progress, THEME.progressBarHeight);
  }}

  // Narration
  if (GRAPH.showNarration) {{
    narrationDiv.textContent = scene.narration || '';
  }} else {{
    narrationDiv.textContent = '';
  }}
}}

function tick(timestamp) {{
  if (playing) {{
    const dt = (timestamp - lastTimestamp) / 1000;
    lastTimestamp = timestamp;
    currentTime += dt;
    if (currentTime >= GRAPH.totalDuration) {{
      currentTime = 0;
    }}
    timelineSlider.value = (currentTime / GRAPH.totalDuration) * 1000;
  }}
  timeDisplay.textContent = formatTime(currentTime) + ' / ' + formatTime(GRAPH.totalDuration);
  render(currentTime);
  requestAnimationFrame(tick);
}}

requestAnimationFrame(tick);
</script>
</body>
</html>"""


def _serve_with_reload(html: str, port: int) -> None:
    """Serve the HTML with a simple HTTP server."""
    import http.server
    import threading
    import tempfile
    import os

    tmpdir = tempfile.mkdtemp(prefix="dsa-anim-")
    path = os.path.join(tmpdir, "index.html")
    with open(path, "w") as f:
        f.write(html)

    os.chdir(tmpdir)
    handler = http.server.SimpleHTTPRequestHandler
    server = http.server.HTTPServer(("", port), handler)

    print(f"Serving preview at http://localhost:{port}")
    webbrowser.open(f"http://localhost:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.shutdown()
