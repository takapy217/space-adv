import streamlit as st
import streamlit.components.v1 as components
import json, re, base64, time
from pathlib import Path
from typing import Union, Dict, Any

# -----------------------------
# ページ設定
# -----------------------------
st.set_page_config(page_title="宇宙船脱出 / Spaceship Escape", layout="centered")

# -----------------------------
# 端末プロファイル（動画枠の高さ制御）
# -----------------------------
DEVICE_PROFILES: Dict[str, Dict[str, Any]] = {
    # 推奨：多端末で安定（ブランク最小）
    # 応急：固定高さ（端末ごとに最適値へ微調整）
    "iPhone SE (Portrait)": {"mode": "fixed", "height": 200},
    "Small Phone":   {"mode": "fixed", "height": 216},
    "Tablet":        {"mode": "fixed", "height": 400},
    "Desktop":       {"mode": "fixed", "height": 400},
    "Standard Phone":{"mode": "fixed", "height": 240},
}

# -----------------------------
# グローバルCSS（共通レイアウト / 余白最適化 / フリッカー抑制）
# ※ iframe 高さは CSS で固定しない（components.html の height を使用）
# -----------------------------
st.markdown(
    """
<style>
/* スマホで最上部が切れないように余白をやや広く */
.block-container{padding-top:2rem !important; padding-bottom:0.8rem !important;}

/* 段落の行間を軽く詰める */
.stMarkdown p{ margin:.35rem 0 !important; }
@media (max-width:480px){ .stMarkdown p{ margin:.28 rem 0 !important; } }

/* 画像は角丸OFF＋統一余白 */
.stImage img{
  display:block !important; width:100% !important; height:auto !important;
  margin:0 0 8px 0 !important; border-radius:0 !important; background:#000;
}

/* ボタンの余白も詰め気味に */
.stButton>button{ margin-top:.10rem !important; margin-bottom:.10rem !important; }

/* （フェードイン用）動画は初期非表示→読み込み完了でふわっと表示 */
.lowflicker-video{
  opacity:0; transition:opacity .18s ease;
  display:block; width:100%; height:100%;
  object-fit:contain; background:#000;
}

/* コンポーネント全体の黒背景でレイアウト差を吸収 */
.lowflicker-wrap{ width:100%; height:100%; background:#000; }
</style>
""",
    unsafe_allow_html=True,
)


def inject_device_css():
    """選択された端末プロファイルに応じて CSS を注入。
    - fixed: iframe 高さは CSS で触らず、video の object-fit を cover に寄せる
    - aspect: アスペクト比ベースのラッパを使い、iframe 高さは自動
    """
    prof = DEVICE_PROFILES.get(st.session_state.get("device_profile", "Auto (Aspect)"))
    if not prof:
        return

    if prof["mode"] == "aspect":
        w, h = prof.get("ratio", (16, 9))
        pad = round(h / w * 100, 5)
        st.markdown(
            f"""
<style>
/* 端末プロファイル: アスペクト比ベース（ブランク最小） */
.video-aspect-wrap{{ position:relative; width:100%; padding-top:{pad}%; background:#000; }}
.video-aspect-wrap > video{{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }}
</style>
""",
            unsafe_allow_html=True,
        )
    else:
        # 固定モード時は黒帯を減らすだけ（高さは components.html で制御）
        st.markdown(
            """
<style>
.lowflicker-video{ object-fit:cover !important; }
</style>
""",
            unsafe_allow_html=True,
        )


# -----------------------------
# ストーリーデータ
# -----------------------------
def load_story(lang: str) -> Dict[str, Any]:
    # 実ファイルに合わせて日本語は jp
    p = Path("story_space_adv_en.json" if lang == "en" else "story_space_adv_jp.json")
    if not p.exists():
        return {
            "intro_text": "JSON not found. Please prepare story file.",
            "chapters": {
                "1": {
                    "text": "Dummy chapter. Please prepare JSON.",
                    "video": "assets/sample.mp4",
                    "choices": [
                        {"text": "▶次へ/Next", "result": {"text": "End", "next": "1", "lp": 0}, "correct": True}
                    ],
                }
            },
        }
    return json.loads(p.read_text(encoding="utf-8"))


# -----------------------------
# セッション初期化 / ヘルパー
# -----------------------------
def init_session():
    defaults = {
        "chapter": "start",
        "lp": 90,
        "selected": None,
        "show_result": False,
        "player_name": "",
        "lang": "jp",  # 既定は日本語（実ファイルに合わせて jp）
        "lp_updated": False,
        "vid_seq": 0,   # 連番（video要素のid用）
        "device_profile": "Standard Phone",  # 端末プロファイル
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def personalize(text: str) -> str:
    return re.sub(r"{player_name}", st.session_state.get("player_name", "あなた"), text or "")


def ensure_asset(path: str) -> Path:
    p = Path(path)
    if not (str(p).startswith("assets/") or str(p).startswith("./assets/")):
        p = Path("assets") / p
    return p


# -----------------------------
# 動画描画（AutoPlay安定・フェードイン）
# -----------------------------
def render_video(path: str, *, autoplay=True, muted=True, loop=False, controls=False, height_pc: int = 360):
    st.session_state.vid_seq += 1
    vid_id = f"v{st.session_state.vid_seq}"

    p = ensure_asset(path)
    if not p.exists():
        st.warning(f"Video not found: {p}")
        return

    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")

    # 端末プロファイル取得
    prof = DEVICE_PROFILES.get(st.session_state.get("device_profile", "Auto (Aspect)")) or {}
    mode = prof.get("mode", "fixed")
    iframe_h = int(prof.get("height") or height_pc)  # 固定モードで使う高さ（既定はPC 360）

    # video 属性
    attrs = []
    if autoplay: attrs.append("autoplay")
    if muted:    attrs.append("muted")
    if loop:     attrs.append("loop")
    if controls: attrs.append("controls")
    attrs.extend([
        "playsinline",
        'preload="auto"',
        "disablepictureinpicture",
        'controlslist="nodownload noplaybackrate nofullscreen"',
    ])
    attr_str = " ".join(attrs)

    if mode == "aspect":
        # アスペクト比ラッパ使用：iframe 高さは小さく、内容で見た目の高さを作る
        html_code = f"""
<div class="video-aspect-wrap">
  <video id="{vid_id}" class="lowflicker-video" {attr_str}>
    <source src="data:video/mp4;base64,{b64}" type="video/mp4">
  </video>
</div>
<script>
(function(){{
  const v = document.getElementById("{vid_id}");
  if(!v) return;
  v.addEventListener('loadeddata', function(){{
    requestAnimationFrame(()=>{{ v.style.opacity = '1'; }});
  }});
  const tryPlay = () => v.play().catch(()=>{{ }});
  if (v.autoplay) {{
    if (v.readyState >= 2) tryPlay(); else v.addEventListener('canplay', tryPlay, {{once:true}});
  }}
}})();
</script>
"""
        components.html(html_code, height=10, scrolling=False)
    else:
        # 固定モード：iframe の height をプロファイル値で直接指定
        html_code = f"""
<div class="lowflicker-wrap">
  <video id="{vid_id}" class="lowflicker-video" {attr_str}
         style="width:100%;height:100%;object-fit:cover;background:#000;">
    <source src="data:video/mp4;base64,{b64}" type="video/mp4">
  </video>
</div>
<script>
(function(){{
  const v = document.getElementById("{vid_id}");
  if(!v) return;
  v.addEventListener('loadeddata', function(){{
    requestAnimationFrame(()=>{{ v.style.opacity = '1'; }});
  }});
  const tryPlay = () => v.play().catch(()=>{{ }});
  if (v.autoplay) {{
    if (v.readyState >= 2) tryPlay(); else v.addEventListener('canplay', tryPlay, {{once:true}});
  }}
}})();
</script>
"""
        components.html(html_code, height=iframe_h, scrolling=False)


# -----------------------------
# メディア描画（文字列/辞書どちらにも対応）
# -----------------------------
def render_media(spec: Union[str, Dict[str, Any]]):
    if not spec:
        return

    if isinstance(spec, str):
        p = ensure_asset(spec)
        if str(p).lower().endswith(".mp4"):
            render_video(str(p))
        else:
            st.image(p, use_container_width=True)
        return

    # 辞書形式
    mtype = (spec.get("type") or "").lower()
    file  = spec.get("file")
    if not file:
        # "video": "...", "image": "..." 形式にも対応
        if isinstance(spec.get("video"), str): mtype, file = "video", spec["video"]
        elif isinstance(spec.get("image"), str): mtype, file = "image", spec["image"]
    if not file:
        return

    if mtype == "video" or str(file).lower().endswith(".mp4"):
        render_video(
            file,
            autoplay=bool(spec.get("autoplay", True)),
            muted=bool(spec.get("muted", True)),
            loop=bool(spec.get("loop", False)),
            controls=bool(spec.get("controls", False)),
        )
    else:
        st.image(ensure_asset(file), use_container_width=True)


def render_chapter_media(chapter: Dict[str, Any]):
    # media > video > image の順で評価
    spec = chapter.get("media") or chapter.get("video") or chapter.get("image")
    render_media(spec)


def render_result_media(chapter: Dict[str, Any], result_data: Dict[str, Any]):
    # result_* > choice_* > video > image
    spec = (
        result_data.get("result_media")
        or result_data.get("result_image")
        or chapter.get("choice_media")
        or chapter.get("choice_image")
        or chapter.get("video")
        or chapter.get("image")
    )
    render_media(spec)


# -----------------------------
# ナビゲーション
# -----------------------------
def go_next_chapter(next_key: str):
    st.session_state.update({
        "chapter": str(next_key),
        "selected": None,
        "show_result": False,
        "lp_updated": False,
    })


def choose_index(i: int):
    st.session_state.update({"selected": i, "show_result": True, "lp_updated": False})


def start_game():
    st.session_state.update({"chapter": "1", "lp": 90, "lp_updated": False})


# -----------------------------
# メイン
# -----------------------------
def main():
    init_session()

    # --- Start ---
    if st.session_state.chapter == "start":
        # 言語選択（ラベル短縮＆縦並び）
        lang_map = {"日本語": "jp", "English": "en"}
        selected_lang = st.radio(
            "      ",
            ("日本語", "English"),
            index=0 if st.session_state.get("lang", "jp") == "jp" else 1,
            horizontal=False,
        )
        st.session_state.lang = lang_map[selected_lang]

        # 言語が決まってから JSON をロード
        story = load_story(st.session_state.lang)

        # 端末プロファイル（復活）
        st.session_state.device_profile = st.selectbox(
            "Device",
            list(DEVICE_PROFILES.keys()),
            index=list(DEVICE_PROFILES.keys()).index(
                st.session_state.get("device_profile", "Auto (Aspect)")
            ),
            help="端末に合わせて動画枠の挙動を選べます",
        )

        # プロファイル選択のあとで CSS 注入
        inject_device_css()

        st.image("assets/img_start.png", use_container_width=True)
        st.markdown("宇宙船脱出 / Spaceship Escape")
        st.button("▶ ゲームを始める / Game start", on_click=start_game)
        st.markdown(personalize(story.get("intro_text", "")))
        return

    # --- Start 以外：常に現在言語で JSON をロード ---
    story = load_story(st.session_state.lang)

    # Game over
    if st.session_state.lp <= 0:
        st.markdown("### 💀 Game Over")
        st.image("assets/img_gameover.png", use_container_width=True)
        if st.button("🔁 Restart"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            init_session()
        return

    # Chapter
    chapter = story["chapters"].get(st.session_state.chapter)
    if not chapter:
        st.error("章データが見つかりません")
        return

    # Result（選択後の結果表示）
    if st.session_state.show_result and st.session_state.selected is not None:
        choice = chapter["choices"][st.session_state.selected]
        result_data = choice["result"]

        if not st.session_state.lp_updated:
            st.session_state.lp = max(0, st.session_state.lp + result_data.get("lp", 0))
            st.session_state.lp_updated = True

        # ここで動画（または画像）→ テキストの順で表示
        render_result_media(chapter, result_data)

        if int(st.session_state.chapter) >= 7:
            st.markdown(f"⏳ Time Left: {st.session_state.lp} min")

        st.markdown(personalize(result_data.get("text", "")))

        if choice.get("correct", False):
            st.button(
                "▶次へ/Next",
                on_click=go_next_chapter,
                args=(str(result_data.get("next", "end")),),
            )
        else:
            st.button(
                "▶選択してください/Choose Again",
                on_click=lambda: st.session_state.update(
                    {"show_result": False, "selected": None, "lp_updated": False}
                ),
            )
        return

    # Normal chapter（動画/画像 → テキスト → 選択肢）
    render_chapter_media(chapter)

    if int(st.session_state.chapter) >= 7:
        st.markdown(f"⏳ Time Left: {st.session_state.lp} min")

    st.markdown(personalize(chapter.get("text", "")))

    choices = chapter.get("choices") or []
    if not choices:
        st.markdown("🎉 Congratulations! Game Clear! 🎉")
        if st.button("🔙 Back to Start"):
            st.balloons()
            time.sleep(2)
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        return

    for i, c in enumerate(choices):
        st.button(personalize(c["text"]), key=f"choice_{i}", on_click=choose_index, args=(i,))


if __name__ == "__main__":
    main()
