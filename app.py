import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import io
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ── Page Config & Custom CSS Styling ──
st.set_page_config(
    page_title="PayPay to MoneyForward 仕分けツール",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium Custom CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    font-family: 'Outfit', 'Noto Sans JP', sans-serif;
}

/* Gradient Title */
.title-container {
    background: linear-gradient(135deg, #1E3A8A, #3B82F6, #06B6D4);
    padding: 2rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    color: white;
    box-shadow: 0 10px 25px rgba(59, 130, 246, 0.2);
}

.title-main {
    font-size: 2.5rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
}

.title-sub {
    font-size: 1.1rem;
    opacity: 0.9;
    margin-top: 0.5rem;
    font-weight: 300;
}

/* Glassmorphism Metric Containers */
div[data-testid="metric-container"] {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 18px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
    backdrop-filter: blur(10px);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

div[data-testid="metric-container"]:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 20px rgba(59, 130, 246, 0.15);
    border-color: rgba(59, 130, 246, 0.4);
}

/* Focused Card for One-by-One Review */
.review-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 2rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
}

.dark-theme .review-card {
    background: rgba(15, 23, 42, 0.4);
}

.review-amount {
    font-size: 2.2rem;
    font-weight: 800;
    color: #3B82F6;
    margin-top: 0.5rem;
}

.review-merchant {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 0.2rem;
}

/* Buttons style */
.stButton>button {
    background: linear-gradient(135deg, #3B82F6, #2563EB) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2) !important;
}

.stButton>button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 12px rgba(37, 99, 235, 0.3) !important;
}

.stDownloadButton>button {
    background: linear-gradient(135deg, #10B981, #059669) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 6px rgba(5, 150, 105, 0.2) !important;
}

.stDownloadButton>button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 12px rgba(5, 150, 105, 0.3) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Constants & Definitions ──
# "未設定" is placed at index 0 as request: No default settings in initial stage
DEBIT_ACCOUNTS = [
    "未設定",
    "消耗品費",
    "通信費",
    "旅費交通費",
    "会議費",
    "接待交際費",
    "仕入高",
    "福利厚生費",
    "支払手数料",
    "雑費",
    "修繕費",
    "水道光熱費",
    "広告宣伝費",
    "荷造運賃",
    "地代家賃",
    "租税公課",
    "新聞図書費",
    "諸会費",
    "事業主貸",
    "普通預金",
    "現金",
    "対象外"
]

CREDIT_ACCOUNTS = [
    "未設定",
    "普通預金",
    "事業主借",
    "現金",
    "売上高",
    "雑収入"
]

TAX_CLASSES = [
    "未設定",
    "対象外",
    "課税仕入 10%",
    "課税仕入 8%",
    "非課税仕入",
    "免税仕入",
    "課税売上 10%",
    "課税売上 8%"
]

DEFAULT_RULES = [
    {
        "keyword": "PayPayポイント運用",
        "debit_account": "対象外",
        "debit_tax_class": "対象外",
        "credit_account": "普通預金",
        "credit_subaccount": "PayPay",
        "is_excluded": True,
        "description": "ポイント運用（プライベート）"
    },
    {
        "keyword": "ローソン",
        "debit_account": "消耗品費",
        "debit_tax_class": "課税仕入 8%",
        "credit_account": "普通預金",
        "credit_subaccount": "PayPay",
        "is_excluded": False,
        "description": "コンビニ食費など"
    },
    {
        "keyword": "Uber Eats",
        "debit_account": "会議費",
        "debit_tax_class": "課税仕入 8%",
        "credit_account": "普通預金",
        "credit_subaccount": "PayPay",
        "is_excluded": False,
        "description": "Uber Eats（会議用食事）"
    },
    {
        "keyword": "Apple",
        "debit_account": "通信費",
        "debit_tax_class": "課税仕入 10%",
        "credit_account": "普通預金",
        "credit_subaccount": "PayPay",
        "is_excluded": False,
        "description": "iCloud・サブスクなど"
    },
    {
        "keyword": "SDベンディング",
        "debit_account": "雑費",
        "debit_tax_class": "課税仕入 8%",
        "credit_account": "普通預金",
        "credit_subaccount": "PayPay",
        "is_excluded": False,
        "description": "自動販売機（飲料等）"
    },
    {
        "keyword": "星宿饭店",
        "debit_account": "会議費",
        "debit_tax_class": "課税仕入 10%",
        "credit_account": "普通預金",
        "credit_subaccount": "PayPay",
        "is_excluded": False,
        "description": "打ち合わせ会食"
    },
    {
        "keyword": "シタラ",
        "debit_account": "会議費",
        "debit_tax_class": "課税仕入 10%",
        "credit_account": "普通預金",
        "credit_subaccount": "PayPay",
        "is_excluded": False,
        "description": "打ち合わせ会食"
    },
    {
        "keyword": "オリーブ亭",
        "debit_account": "会議費",
        "debit_tax_class": "課税仕入 10%",
        "credit_account": "普通預金",
        "credit_subaccount": "PayPay",
        "is_excluded": False,
        "description": "打ち合わせ会食"
    },
    {
        "keyword": "瀬佐味亭",
        "debit_account": "会議費",
        "debit_tax_class": "課税仕入 10%",
        "credit_account": "普通預金",
        "credit_subaccount": "PayPay",
        "is_excluded": False,
        "description": "打ち合わせ会食"
    },
    {
        "keyword": "縁",
        "debit_account": "接待交際費",
        "debit_tax_class": "課税仕入 10%",
        "credit_account": "普通預金",
        "credit_subaccount": "PayPay",
        "is_excluded": False,
        "description": "接待交際会食"
    }
]

RULES_FILE_PATH = "rules.json"

# ── File Helper Functions ──

def load_rules():
    if os.path.exists(RULES_FILE_PATH):
        try:
            with open(RULES_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"ルールファイルの読み込みに失敗しました: {e}")
            return DEFAULT_RULES.copy()
    else:
        save_rules(DEFAULT_RULES)
        return DEFAULT_RULES.copy()

def save_rules(rules):
    try:
        with open(RULES_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"ルールファイルの保存に失敗しました: {e}")

def parse_amount(val):
    if pd.isna(val) or val == "-" or val == "":
        return 0
    val_str = str(val).replace(",", "").strip()
    try:
        return int(float(val_str))
    except ValueError:
        return 0

def load_paypay_csv(file_path):
    try:
        df = pd.read_csv(file_path, encoding="utf-8")
        required_cols = ["取引日", "取引先", "取引内容", "出金金額（円）", "入金金額（円）"]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"CSVに必要なカラム '{col}' が見つかりません。")
                return None
                
        # Filter out PayPay points transactions (hide them entirely from loading)
        if "取引方法" in df.columns:
            df = df[df["取引方法"] != "PayPayポイント"].copy()
            
        return df
    except Exception as e:
        st.error(f"PayPay CSVの読み込みエラー: {e}")
        return None

def apply_categorization_rules(paypay_df, rules, settings):
    rows = []
    
    # Sort settings (unmatched fallbacks are "未設定")
    default_out_debit = settings.get("default_out_debit", "未設定")
    default_out_credit = settings.get("default_out_credit", "未設定")
    default_out_credit_sub = settings.get("default_out_credit_sub", "")
    default_out_tax_class = settings.get("default_out_tax_class", "未設定")
    
    default_in_debit = settings.get("default_in_debit", "未設定")
    default_in_debit_sub = settings.get("default_in_debit_sub", "")
    default_in_credit = settings.get("default_in_credit", "未設定")
    default_in_tax_class = settings.get("default_in_tax_class", "未設定")
    
    exclude_charges = settings.get("exclude_charges", True)
    exclude_points = settings.get("exclude_points", True)
    exclude_investments = settings.get("exclude_investments", True)
    exclude_transfers = settings.get("exclude_transfers", True)
    
    for idx, row in paypay_df.iterrows():
        date_str = str(row["取引日"]).strip()
        try:
            dt = datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
            formatted_date = dt.strftime("%Y/%m/%d")
        except ValueError:
            try:
                dt = datetime.strptime(date_str, "%Y/%m/%d")
                formatted_date = dt.strftime("%Y/%m/%d")
            except ValueError:
                formatted_date = date_str.split(" ")[0]
                
        out_amount = parse_amount(row["出金金額（円）"])
        in_amount = parse_amount(row["入金金額（円）"])
        amount = out_amount if out_amount > 0 else in_amount
        
        tx_type = str(row["取引内容"]).strip()
        merchant = str(row["取引先"]).strip()
        method = str(row["取引方法"]).strip()
        tx_id = str(row.get("取引番号", "")).strip()
        
        debit_acc = "未設定"
        debit_sub = ""
        debit_tax = "未設定"
        credit_acc = "未設定"
        credit_sub = ""
        credit_tax = "対象外"
        is_excluded = False
        
        # Check rule match
        matched_rule = None
        for rule in rules:
            if rule["keyword"].lower() in merchant.lower():
                matched_rule = rule
                break
                
        if matched_rule:
            is_excluded = matched_rule.get("is_excluded", False)
            if out_amount > 0:
                debit_acc = matched_rule.get("debit_account", default_out_debit)
                debit_sub = matched_rule.get("debit_subaccount", "")
                debit_tax = matched_rule.get("debit_tax_class", default_out_tax_class)
                credit_acc = matched_rule.get("credit_account", default_out_credit)
                credit_sub = matched_rule.get("credit_subaccount", default_out_credit_sub)
                credit_tax = "対象外"
            else: # Inflow
                debit_acc = matched_rule.get("debit_account", default_in_debit)
                debit_sub = matched_rule.get("debit_subaccount", default_in_debit_sub)
                debit_tax = "対象外"
                credit_acc = matched_rule.get("credit_account", default_in_credit)
                credit_sub = matched_rule.get("credit_subaccount", "")
                credit_tax = matched_rule.get("credit_tax_class", default_in_tax_class)
        else:
            # Fallback to type defaults (which defaults to "未設定" as requested)
            if out_amount > 0:
                debit_acc = default_out_debit
                debit_sub = ""
                debit_tax = default_out_tax_class
                credit_acc = default_out_credit
                credit_sub = default_out_credit_sub
                credit_tax = "対象外"
                
                # Check category specific automatic exclusions
                if tx_type == "投資":
                    is_excluded = exclude_investments
                    debit_acc = "対象外"
                    debit_tax = "対象外"
                elif tx_type == "送った金額":
                    is_excluded = True # Peer-to-peer transfers are excluded by default
                    debit_acc = "対象外"
                    debit_tax = "対象外"
            else:
                # Inflow (money increases): Unconditionally excluded by default as requested
                is_excluded = True
                debit_acc = "対象外"
                debit_sub = ""
                debit_tax = "対象外"
                credit_acc = "対象外"
                credit_sub = ""
                credit_tax = "対象外"
                
                if tx_type == "チャージ":
                    debit_acc = "普通預金"
                    debit_sub = "PayPay"
                    credit_acc = "普通預金"
                    if "ゆうちょ" in method:
                        credit_sub = "ゆうちょ銀行"
                    else:
                        credit_sub = method.replace("PayPay", "").strip()
                elif tx_type == "ポイント、残高の獲得":
                    debit_acc = "普通預金"
                    debit_sub = "PayPay"
                    credit_acc = "雑収入"
                    credit_tax = "対象外"
                elif tx_type == "受け取った金額":
                    debit_acc = "普通預金"
                    debit_sub = "PayPay"
                    credit_acc = "対象外"
                    credit_tax = "対象外"
                    
        desc = f"{merchant} ({tx_type})"
        memo = f"利用方法: {method} | 取引番号: {tx_id}"
        
        rows.append({
            "original_index": idx,
            "取引No": idx + 1,
            "取引日": formatted_date,
            "借方勘定科目": debit_acc,
            "借方補助科目": debit_sub,
            "借方部門": "",
            "借方取引先": "",
            "借方税区分": debit_tax,
            "借方インボイス": "",
            "借方金額(円)": amount,
            "借方税額": 0,
            "貸方勘定科目": credit_acc,
            "貸方補助科目": credit_sub,
            "貸方部門": "",
            "貸方取引先": "",
            "貸方税区分": credit_tax,
            "貸方インボイス": "",
            "貸方金額(円)": amount,
            "貸方税額": 0,
            "摘要": desc,
            "仕訳メモ": memo,
            "タグ": "",
            "対象外": is_excluded,
            "is_manually_edited": False
        })
        
    return pd.DataFrame(rows)

# ── Header ──
st.markdown("""
<div class="title-container">
    <div class="title-main">📱 PayPay 仕分けツール for マネーフォワード</div>
    <div class="title-sub">PayPayの取引明細を順々に確認・仕分けしながら、マネーフォワード確定申告形式のCSVを作成します。</div>
</div>
""", unsafe_allow_html=True)

# Folders setup
os.makedirs("data", exist_ok=True)
os.makedirs("output", exist_ok=True)

rules = load_rules()
data_files = [f for f in os.listdir("data") if f.endswith(".csv") and not f.endswith("_checkpoint.csv")]

# ── Sidebar Settings ──
with st.sidebar:
    st.header("📂 ファイル選択 & 設定")
    
    selected_file = None
    if len(data_files) > 0:
        selected_file_name = st.selectbox("data/ 直下のCSVファイルを選択", data_files)
        selected_file = os.path.join("data", selected_file_name)
    else:
        st.info("data/ ディレクトリにCSVファイルがありません。")
        
    uploaded_file = st.file_uploader("または、PayPay CSVファイルをアップロード", type=["csv"])
    if uploaded_file is not None:
        save_path = os.path.join("data", uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        selected_file = save_path
        st.success(f"ファイルを保存しました: {uploaded_file.name}")
        st.rerun()

    st.subheader("⚙️ 自動除外設定 (Filters)")
    exclude_investments = st.checkbox("ポイント運用 (投資) を自動除外", value=True)
    exclude_points = st.checkbox("ポイント・残高獲得を自動除外", value=True)
    exclude_charges = st.checkbox("チャージ取引を自動除外", value=True)
    exclude_transfers = st.checkbox("送金・受取 (個人間) を自動除外", value=True)
    
    st.subheader("🛠️ 初期仕分け設定")
    st.markdown("<small>※『未設定』にすると、ルールに一致しない行は空欄（分類待ち）になります（推奨）。</small>", unsafe_allow_html=True)
    
    default_out_debit = st.selectbox("デフォルトの経費科目 (借方)", DEBIT_ACCOUNTS, index=DEBIT_ACCOUNTS.index("未設定"))
    default_out_tax_class = st.selectbox("デフォルトの経費税区分 (借方)", TAX_CLASSES, index=TAX_CLASSES.index("未設定"))
    default_out_credit = st.selectbox("デフォルトの支払元科目 (貸方)", CREDIT_ACCOUNTS, index=CREDIT_ACCOUNTS.index("未設定"))
    default_out_credit_sub = st.text_input("デフォルトの支払元補助科目", value="")
    
    default_in_debit = st.selectbox("デフォルトの受取先科目 (借方)", DEBIT_ACCOUNTS, index=DEBIT_ACCOUNTS.index("未設定"))
    default_in_debit_sub = st.text_input("デフォルトの受取先補助科目", value="")
    default_in_credit = st.selectbox("デフォルトの収入科目 (貸方)", CREDIT_ACCOUNTS, index=CREDIT_ACCOUNTS.index("未設定"))
    default_in_tax_class = st.selectbox("デフォルトの収入税区分 (貸方)", TAX_CLASSES, index=TAX_CLASSES.index("未設定"))

    settings = {
        "exclude_investments": exclude_investments,
        "exclude_points": exclude_points,
        "exclude_charges": exclude_charges,
        "exclude_transfers": exclude_transfers,
        "default_out_debit": default_out_debit,
        "default_out_tax_class": default_out_tax_class,
        "default_out_credit": default_out_credit,
        "default_out_credit_sub": default_out_credit_sub,
        "default_in_debit": default_in_debit,
        "default_in_debit_sub": default_in_debit_sub,
        "default_in_credit": default_in_credit,
        "default_in_tax_class": default_in_tax_class
    }
    
    st.divider()
    st.subheader("🔄 作業データのリセット")
    if st.button("🚨 最初期状態からやり直す (Reset All)", help="現在のファイルのチェックポイント（進捗）を削除し、完全にリセットします。"):
        if selected_file:
            checkpoint_path = selected_file.replace(".csv", "_checkpoint.csv")
            if os.path.exists(checkpoint_path):
                try:
                    os.remove(checkpoint_path)
                    st.toast("チェックポイントファイルを削除しました。", icon="🗑️")
                except Exception as e:
                    st.error(f"ファイル削除に失敗しました: {e}")
            if "df" in st.session_state:
                del st.session_state.df
            st.session_state.wizard_idx = 0
            st.success("作業データを完全にリセットしました。リロードします...")
            st.rerun()
        else:
            st.warning("対象ファイルが選択されていません。")

# ── Main Flow ──
if selected_file:
    checkpoint_file = selected_file.replace(".csv", "_checkpoint.csv")
    
    # Reload logic when selected file changes
    if "current_file" not in st.session_state or st.session_state.current_file != selected_file:
        st.session_state.current_file = selected_file
        st.session_state.wizard_idx = 0 # reset stepper
        
        if os.path.exists(checkpoint_file):
            try:
                st.session_state.df = pd.read_csv(checkpoint_file, encoding="utf-8")
                st.session_state.df["対象外"] = st.session_state.df["対象外"].apply(lambda x: str(x).strip().lower() in ('true', '1', '1.0'))
                st.session_state.df["is_manually_edited"] = st.session_state.df["is_manually_edited"].apply(lambda x: str(x).strip().lower() in ('true', '1', '1.0'))
                st.toast("チェックポイントから進捗を復元しました！", icon="💾")
            except Exception as e:
                st.error(f"チェックポイントのロードエラー。再生成します。: {e}")
                paypay_df = load_paypay_csv(selected_file)
                if paypay_df is not None:
                    st.session_state.df = apply_categorization_rules(paypay_df, rules, settings)
        else:
            paypay_df = load_paypay_csv(selected_file)
            if paypay_df is not None:
                st.session_state.df = apply_categorization_rules(paypay_df, rules, settings)
                st.toast("明細をインポートしました！(未設定項目は空欄になります)", icon="✨")

    if "df" in st.session_state:
        df = st.session_state.df

        # Metrics Calculations
        total_rows = len(df)
        excluded_rows = df["対象外"].sum()
        active_rows = total_rows - excluded_rows
        
        # Count confirmed active rows (manually checked by user)
        confirmed_active_rows = df[(df["対象外"] == False) & (df["is_manually_edited"] == True)].shape[0]
        
        # Calculate how many active rows are unsettled (unreviewed AND still "未設定")
        unsettled_active_rows = df[
            (df["対象外"] == False) & 
            (df["is_manually_edited"] == False) & (
                (df["借方勘定科目"] == "未設定") | 
                (df["貸方勘定科目"] == "未設定")
            )
        ]
        unsettled_count = len(unsettled_active_rows)
        
        # Progress counts rows that are EITHER rule-categorized OR manually confirmed
        progress_count = active_rows - unsettled_count

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("総明細数", f"{total_rows} 件")
        c2.metric("仕分け対象件数", f"{active_rows} 件", f"除外: {excluded_rows}件", delta_color="inverse")
        c3.metric("確認・処理済み", f"{confirmed_active_rows} / {active_rows} 件")
        c4.metric("処理待ち (未設定)", f"{unsettled_count} 件", delta_color="off" if unsettled_count == 0 else "inverse")
        
        # Progress Bar based on progress_count (clipped between 0.0 and 1.0)
        progress_ratio = progress_count / max(1, active_rows)
        progress_ratio = min(1.0, max(0.0, float(progress_ratio)))
        progress_val = int(progress_ratio * 100)
        st.progress(progress_ratio, text=f"仕分け進捗率: {progress_val}% (自動ルール適用分含む)")

        # ── Mode Selection (Sequential vs Bulk) ──
        st.divider()
        mode = st.radio("🛠️ 作業モードを選択してください", ["📖 一件ずつ確認して仕分ける (推奨・順次処理)", "📊 一覧表でまとめて編集する (一括処理)"], horizontal=True)

        tab_editor, tab_rules, tab_charts = st.tabs(["📝 仕分け作業エリア", "🛠️ 自動仕分けルール管理", "📈 グラフ・統計レポート"])

        # ── TAB 1: Main Work Area ──
        with tab_editor:
            if mode == "📖 一件ずつ確認して仕分ける (推奨・順次処理)":
                st.subheader("📖 順次仕分けウィザード")
                st.caption("明細を1件ずつ確認し、勘定科目を選択して「確定して次へ」進みます。")
                
                # Keyboard Shortcut Help Banner
                st.info("💡 **便利なショートカットキーが使えます:**\n"
                        "入力欄以外の場所で **`←`（左矢印キー）** を押すと「確定して次へ」、"
                        "**`→`（右矢印キー）** を押すと「対象外にして次へ」が進みます。\n"
                        "（※勘定科目選択中や文字入力中は誤操作を防ぐため無効になります）")
                
                # Inject JS for keyboard shortcuts in Wizard mode (handles both main window and iframe focus)
                import streamlit.components.v1 as components
                components.html("""
                <script>
                const doc1 = window.document;
                const doc2 = window.parent.document;
                
                const handler = function(e) {
                    // Check active elements in both documents to prevent triggering while typing
                    const activeEl = doc1.activeElement || doc2.activeElement;
                    if (activeEl && (
                        activeEl.tagName === 'INPUT' || 
                        activeEl.tagName === 'TEXTAREA' || 
                        activeEl.tagName === 'SELECT' || 
                        activeEl.isContentEditable ||
                        activeEl.getAttribute('role') === 'combobox' ||
                        activeEl.getAttribute('role') === 'listbox' ||
                        activeEl.getAttribute('role') === 'option' ||
                        activeEl.closest('.stSelectbox') ||
                        activeEl.closest('.stTextInput')
                    )) {
                        return; // Ignore if typing or selecting
                    }
                    
                    if (e.key === 'ArrowRight') {
                        // Find exclude button in both documents
                        const buttons = Array.from(doc1.querySelectorAll('button')).concat(Array.from(doc2.querySelectorAll('button')));
                        const excludeBtn = buttons.find(btn => btn.textContent.includes('対象外にして次へ') || btn.textContent.includes('対象外'));
                        if (excludeBtn) {
                            e.preventDefault();
                            excludeBtn.click();
                        }
                    } else if (e.key === 'ArrowLeft') {
                        // Find confirm button in both documents
                        const buttons = Array.from(doc1.querySelectorAll('button')).concat(Array.from(doc2.querySelectorAll('button')));
                        const confirmBtn = buttons.find(btn => btn.textContent.includes('確定して次へ') || btn.textContent.includes('確定'));
                        if (confirmBtn) {
                            e.preventDefault();
                            confirmBtn.click();
                        }
                    }
                };
                
                // Cleanup old handlers to prevent multiple registrations
                if (window._agy_iframe_handler) {
                    doc1.removeEventListener('keydown', window._agy_iframe_handler);
                }
                if (window.parent._agy_parent_handler) {
                    doc2.removeEventListener('keydown', window.parent._agy_parent_handler);
                }
                
                // Save references and bind
                window._agy_iframe_handler = handler;
                window.parent._agy_parent_handler = handler;
                
                doc1.addEventListener('keydown', handler);
                doc2.addEventListener('keydown', handler);
                </script>
                """, height=0, width=0)
                
                # Filter for wizard
                wizard_filter = st.selectbox("仕分けウィザードの表示対象", ["未確認・処理待ちの明細のみ (未設定のみ)", "すべての仕分け対象明細"])
                
                # Filter data for wizard
                if wizard_filter == "未確認・処理待ちの明細のみ (未設定のみ)":
                    wizard_df = df[
                        (df["対象外"] == False) & 
                        (df["is_manually_edited"] == False) & (
                            (df["借方勘定科目"] == "未設定") | 
                            (df["貸方勘定科目"] == "未設定")
                        )
                    ].copy()
                else:
                    wizard_df = df[df["対象外"] == False].copy()
                
                if len(wizard_df) == 0:
                    st.success("🎉 条件に一致する処理待ちの明細はありません！すべて仕分けが完了しています。")
                    if st.button("もう一度最初から確認する (すべての仕分け対象明細を表示)"):
                        st.session_state.wizard_idx = 0
                else:
                    # Keep track of index safety
                    if "wizard_idx" not in st.session_state:
                        st.session_state.wizard_idx = 0
                        
                    if st.session_state.wizard_idx >= len(wizard_df):
                        st.session_state.wizard_idx = max(0, len(wizard_df) - 1)
                        
                    idx_in_wizard = st.session_state.wizard_idx
                    current_row = wizard_df.iloc[idx_in_wizard]
                    target_df_idx = current_row.name # Use actual dataframe index label to avoid mismatch/growing rows
                    
                    # Wizard Header
                    st.write(f"**明細 {idx_in_wizard + 1} / {len(wizard_df)} 件目**")
                    
                    # Safe string conversion for NaN fields
                    memo_str = str(current_row['仕訳メモ']) if not pd.isna(current_row['仕訳メモ']) else ""
                    tx_id_str = memo_str.split('取引番号: ')[-1] if '取引番号: ' in memo_str else ''
                    method_str = memo_str.split(' ｜ ')[0] if ' ｜ ' in memo_str else memo_str
                    
                    summary_str = str(current_row['摘要']) if not pd.isna(current_row['摘要']) else ""
                    merchant_str = summary_str.split(' (')[0] if ' (' in summary_str else summary_str
                    
                    # Transaction Card UI
                    st.markdown(f"""
                    <div class="review-card">
                        <div style="font-size:0.9rem; opacity:0.7;">取引日: {current_row['取引日']} ｜ 取引番号: {tx_id_str}</div>
                        <div class="review-merchant">{merchant_str}</div>
                        <div style="font-size:0.9rem; opacity:0.8; margin-bottom:1rem;">{method_str}</div>
                        <div style="font-size:0.9rem;">金額</div>
                        <div class="review-amount">¥ {current_row['借方金額(円)']:,.0f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Wizard Inputs Form
                    with st.form(f"wizard_form_{target_df_idx}"):
                        w_col1, w_col2 = st.columns(2)
                        
                        with w_col1:
                            # 借方勘定科目
                            current_debit = current_row["借方勘定科目"]
                            debit_default_idx = DEBIT_ACCOUNTS.index(current_debit) if current_debit in DEBIT_ACCOUNTS else 0
                            w_debit = st.selectbox("借方勘定科目 (経費科目)", DEBIT_ACCOUNTS, index=debit_default_idx)
                            
                            # 借方補助科目
                            w_debit_sub = st.text_input("借方補助科目", value=str(current_row["借方補助科目"]) if not pd.isna(current_row["借方補助科目"]) else "")
                            
                            # 借方税区分
                            current_tax = current_row["借方税区分"]
                            tax_default_idx = TAX_CLASSES.index(current_tax) if current_tax in TAX_CLASSES else 0
                            w_debit_tax = st.selectbox("借方税区分", TAX_CLASSES, index=tax_default_idx)
                            
                        with w_col2:
                            # 貸方勘定科目
                            current_credit = current_row["貸方勘定科目"]
                            credit_default_idx = CREDIT_ACCOUNTS.index(current_credit) if current_credit in CREDIT_ACCOUNTS else 0
                            w_credit = st.selectbox("貸方勘定科目 (資金支払元)", CREDIT_ACCOUNTS, index=credit_default_idx)
                            
                            # 貸方補助科目
                            w_credit_sub = st.text_input("貸方補助科目", value=str(current_row["貸方補助科目"]) if not pd.isna(current_row["貸方補助科目"]) else "")
                            
                            # Exclude toggle
                            w_is_excluded = st.checkbox("この明細を除外する (確定申告の対象外にする)", value=bool(current_row["対象外"]))
                            
                        w_desc = st.text_input("摘要 (取引内容説明)", value=summary_str)
                        w_memo = st.text_input("仕訳メモ", value=memo_str)
                        
                        # Form Action Buttons (Inside Form to trigger single submit)
                        f_btn_col1, f_btn_col2, f_btn_col3 = st.columns([1, 1, 1])
                        with f_btn_col1:
                            submit_confirm = st.form_submit_button("✅ 確定して次へ")
                        with f_btn_col2:
                            submit_skip = st.form_submit_button("⏭️ スキップして次へ")
                        with f_btn_col3:
                            submit_exclude = st.form_submit_button("🗑️ 対象外にして次へ")
                            
                        if submit_confirm:
                            # Update master dataframe in-place at correct index
                            df.loc[target_df_idx, "借方勘定科目"] = w_debit
                            df.loc[target_df_idx, "借方補助科目"] = w_debit_sub
                            df.loc[target_df_idx, "借方税区分"] = w_debit_tax
                            df.loc[target_df_idx, "貸方勘定科目"] = w_credit
                            df.loc[target_df_idx, "貸方補助科目"] = w_credit_sub
                            df.loc[target_df_idx, "摘要"] = w_desc
                            df.loc[target_df_idx, "仕訳メモ"] = w_memo
                            df.loc[target_df_idx, "対象外"] = w_is_excluded
                            df.loc[target_df_idx, "is_manually_edited"] = True
                            
                            # Save checkpoint
                            st.session_state.df = df
                            df.to_csv(checkpoint_file, encoding="utf-8", index=False)
                            
                            # Move to next
                            st.session_state.wizard_idx = (idx_in_wizard + 1) % len(wizard_df)
                            st.toast("仕分けを保存しました！", icon="✅")
                            st.rerun()
                            
                        if submit_skip:
                            st.session_state.wizard_idx = (idx_in_wizard + 1) % len(wizard_df)
                            st.rerun()
                            
                        if submit_exclude:
                            # Exclude correctly in-place
                            df.loc[target_df_idx, "対象外"] = True
                            df.loc[target_df_idx, "is_manually_edited"] = True
                            st.session_state.df = df
                            df.to_csv(checkpoint_file, encoding="utf-8", index=False)
                            st.session_state.wizard_idx = (idx_in_wizard + 1) % len(wizard_df)
                            st.toast("この明細を対象外に設定しました。", icon="🗑️")
                            st.rerun()
                            
                    # Nav buttons (Outside Form to allow simple page turning)
                    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 4])
                    with nav_col1:
                        if st.button("◀ 前の明細へ", disabled=(idx_in_wizard == 0)):
                            st.session_state.wizard_idx = idx_in_wizard - 1
                            st.rerun()
                    with nav_col2:
                        if st.button("次の明細へ ▶", disabled=(idx_in_wizard == len(wizard_df) - 1)):
                            st.session_state.wizard_idx = idx_in_wizard + 1
                            st.rerun()
                            
            else:
                # ── Bulk Table Editor ──
                st.subheader("📊 一括仕分けエディタ")
                st.caption("エクセル感覚で直接表をダブルクリックして値を書き換えられます。未設定セルは目立つように赤・オレンジ等で警告表示されます。")
                
                # Filters
                f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
                with f_col1:
                    filter_status = st.selectbox(
                        "表示フィルター", 
                        [
                            "すべて", 
                            "マネーフォワード取込対象のみ (除外を除く)", 
                            "未仕分けのみ (未設定)", 
                            "確認・編集済みのみ", 
                            "対象外のみ"
                        ]
                    )
                with f_col2:
                    filter_account = st.selectbox("借方科目で絞り込み", ["すべて"] + DEBIT_ACCOUNTS)
                with f_col3:
                    search_query = st.text_input("摘要 / 仕訳メモで検索")

                filtered_df = df.copy()
                if filter_status == "マネーフォワード取込対象のみ (除外を除く)":
                    filtered_df = filtered_df[filtered_df["対象外"] == False]
                elif filter_status == "未仕分けのみ (未設定)":
                    filtered_df = filtered_df[(filtered_df["対象外"] == False) & (
                        (filtered_df["借方勘定科目"] == "未設定") | 
                        (filtered_df["貸方勘定科目"] == "未設定")
                    )]
                elif filter_status == "確認・編集済みのみ":
                    filtered_df = filtered_df[filtered_df["is_manually_edited"] == True]
                elif filter_status == "対象外のみ":
                    filtered_df = filtered_df[filtered_df["対象外"] == True]
                    
                if filter_account != "すべて":
                    filtered_df = filtered_df[filtered_df["借方勘定科目"] == filter_account]
                    
                if search_query:
                    filtered_df = filtered_df[
                        filtered_df["摘要"].str.contains(search_query, case=False, na=False) |
                        filtered_df["仕訳メモ"].str.contains(search_query, case=False, na=False)
                    ]

                # Editor setup
                editor_config = {
                    "original_index": None,
                    "is_manually_edited": None,
                    "取引No": st.column_config.NumberColumn("No", disabled=True, width="small"),
                    "取引日": st.column_config.TextColumn("取引日", width="medium"),
                    "借方勘定科目": st.column_config.SelectboxColumn("借方勘定科目 (経費)", options=DEBIT_ACCOUNTS, width="medium", required=True),
                    "借方補助科目": st.column_config.TextColumn("借方補助科目", width="small"),
                    "借方税区分": st.column_config.SelectboxColumn("借方税区分", options=TAX_CLASSES, width="medium"),
                    "借方金額(円)": st.column_config.NumberColumn("金額(円)", disabled=True, format="¥%d", width="small"),
                    "貸方勘定科目": st.column_config.SelectboxColumn("貸方勘定科目 (資金元)", options=CREDIT_ACCOUNTS, width="medium", required=True),
                    "貸方補助科目": st.column_config.TextColumn("貸方補助科目", width="small"),
                    "貸方税区分": st.column_config.SelectboxColumn("貸方税区分", options=TAX_CLASSES, width="small"),
                    "摘要": st.column_config.TextColumn("摘要 (店舗名等)", width="large"),
                    "仕訳メモ": st.column_config.TextColumn("仕訳メモ", width="large"),
                    "タグ": st.column_config.TextColumn("タグ", width="small"),
                    "対象外": st.column_config.CheckboxColumn("対象外 (除外)", width="small")
                }

                # Display interactive editor
                edited_data = st.data_editor(
                    filtered_df,
                    column_config=editor_config,
                    use_container_width=True,
                    num_rows="dynamic",
                    key="transactions_editor_bulk"
                )
                
                # Actions Buttons
                btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])
                with btn_col1:
                    if st.button("💾 変更を保存 (Save Changes)"):
                        for idx, row in edited_data.iterrows():
                            orig_idx = row["original_index"]
                            orig_row = df.loc[orig_idx]
                            
                            changed = False
                            columns_to_check = ["借方勘定科目", "借方補助科目", "借方税区分", "貸方勘定科目", "貸方補助科目", "摘要", "仕訳メモ", "対象外"]
                            for col in columns_to_check:
                                if str(row[col]) != str(orig_row[col]):
                                    changed = True
                                    break
                                    
                            df.loc[orig_idx] = row
                            if changed:
                                df.loc[orig_idx, "is_manually_edited"] = True
                                
                        df["貸方金額(円)"] = df["借方金額(円)"]
                        st.session_state.df = df
                        df.to_csv(checkpoint_file, encoding="utf-8", index=False)
                        st.success("変更を保存しました！")
                        st.rerun()
                        
                with btn_col2:
                    if st.button("🔄 変更を破棄してリセット"):
                        if os.path.exists(checkpoint_file):
                            os.remove(checkpoint_file)
                        st.session_state.df = apply_categorization_rules(load_paypay_csv(selected_file), rules, settings)
                        st.success("最初から再生成しました。")
                        st.rerun()

            st.divider()
            
            # ── Export Panel ──
            st.subheader("📤 マネーフォワード用CSV出力")
            st.write("仕分け完了した明細のみをエクスポートします（対象外にチェックが入っている行は除外されます）。")
            
            # Filters rows for export: exclude if boolean flag is True, or if accounts are explicitly set to "対象外"
            export_df = df[
                (df["対象外"] == False) & 
                (df["借方勘定科目"] != "対象外") & 
                (df["貸方勘定科目"] != "対象外")
            ].copy()
            
            if len(export_df) > 0:
                # Check for remaining "未設定"
                unsettled_export = export_df[
                    (export_df["借方勘定科目"] == "未設定") | 
                    (export_df["貸方勘定科目"] == "未設定") |
                    (export_df["借方税区分"] == "未設定")
                ]
                
                if len(unsettled_export) > 0:
                    st.warning(f"⚠️ **未仕分け項目が残っています:** 出力対象の中に、まだ勘定科目や税区分が「未設定」の明細が **{len(unsettled_export)}件** あります。このまま出力すると、未設定のままCSVが作成されます。")
                    with st.expander("未設定の明細を確認"):
                        st.dataframe(unsettled_export[["取引日", "摘要", "借方金額(円)", "借方勘定科目", "貸方勘定科目"]])
                else:
                    st.success("✅ すべての明細の仕分けが完了しています！エクスポート準備完了。")
                
                # Re-index Transaction numbers
                export_df = export_df.sort_values(by="取引日")
                export_df["取引No"] = range(1, len(export_df) + 1)
                
                # Expected 27 columns for MoneyForward
                mf_columns = [
                    "取引No", "取引日", 
                    "借方勘定科目", "借方補助科目", "借方部門", "借方取引先", "借方税区分", "借方インボイス", "借方金額(円)", "借方税額",
                    "貸方勘定科目", "貸方補助科目", "貸方部門", "貸方取引先", "貸方税区分", "貸方インボイス", "貸方金額(円)", "貸方税額",
                    "摘要", "仕訳メモ", "タグ", 
                    "MF仕訳タイプ", "決算整理仕訳", "作成日時", "作成者", "最終更新日時", "最終更新者"
                ]
                
                for col in mf_columns:
                    if col not in export_df.columns:
                        export_df[col] = ""
                
                # Clean up "未設定" entries to blank before export, so MF imports them cleanly (as blank if not filled)
                final_export = export_df[mf_columns].copy()
                final_export["借方勘定科目"] = final_export["借方勘定科目"].replace("未設定", "")
                final_export["貸方勘定科目"] = final_export["貸方勘定科目"].replace("未設定", "")
                final_export["借方税区分"] = final_export["借方税区分"].replace("未設定", "")
                final_export["貸方税区分"] = final_export["貸方税区分"].replace("未設定", "")
                
                # Preview Table
                with st.expander("📋 マネーフォワード出力用CSV プレビュー (対象外を除く全データ)", expanded=True):
                    st.dataframe(final_export, use_container_width=True)
                
                # CP932 / Shift-JIS conversion with CRLF endings
                csv_buffer = io.BytesIO()
                final_export.to_csv(csv_buffer, index=False, encoding="cp932", errors="replace", lineterminator="\r\n")
                csv_bytes = csv_buffer.getvalue()
                
                col_btn1, col_btn2 = st.columns([1, 1])
                with col_btn1:
                    st.download_button(
                        label="📥 ブラウザからCSVをダウンロード (Download)",
                        data=csv_bytes,
                        file_name="mf_journal_paypay.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with col_btn2:
                    if st.button("💾 ローカルの output/ フォルダに保存 (Save Local)", use_container_width=True):
                        output_local_path = os.path.join("output", f"mf_journal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                        try:
                            with open(output_local_path, "wb") as f:
                                f.write(csv_bytes)
                            st.toast(f"ファイルを保存しました: {output_local_path}", icon="💾")
                            st.success(f"ローカルの `output/` ディレクトリに保存しました: `{output_local_path}`")
                        except Exception as e:
                            st.error(f"ファイルの保存に失敗しました: {e}")
            else:
                st.warning("出力対象の明細がありません（すべて対象外に設定されています）。")

        # ── TAB 2: Rules Manager ──
        with tab_rules:
            st.subheader("🛠️ 自動仕分けルールの管理")
            st.write("特定の取引先（キーワード）に一致したとき、自動で勘定科目を設定するルールを管理します。")
            
            # Rule Creator Form
            with st.form("new_rule_form_v2", clear_on_submit=True):
                st.write("➕ 自動仕分けルールの追加")
                r_col1, r_col2, r_col3 = st.columns(3)
                with r_col1:
                    new_kw = st.text_input("取引先キーワード (例: ライフ, タイムズ)")
                    new_desc = st.text_input("説明・メモ (例: 消耗品、オフィス消耗品等)")
                with r_col2:
                    new_debit = st.selectbox("借方勘定科目 (経費)", DEBIT_ACCOUNTS, index=DEBIT_ACCOUNTS.index("消耗品費") if "消耗品費" in DEBIT_ACCOUNTS else 0)
                    new_tax = st.selectbox("借方税区分", TAX_CLASSES, index=TAX_CLASSES.index("課税仕入 10%") if "課税仕入 10%" in TAX_CLASSES else 0)
                with r_col3:
                    new_credit = st.selectbox("貸方勘定科目 (支払元)", CREDIT_ACCOUNTS, index=CREDIT_ACCOUNTS.index("普通預金") if "普通預金" in CREDIT_ACCOUNTS else 0)
                    new_is_ex = st.checkbox("この取引を自動的に除外 (対象外にする)", value=False)
                
                submit_rule = st.form_submit_button("ルールを保存・適用")
                if submit_rule:
                    if new_kw.strip() == "":
                        st.error("キーワードを入力してください。")
                    else:
                        new_rule = {
                            "keyword": new_kw.strip(),
                            "debit_account": new_debit,
                            "debit_tax_class": new_tax,
                            "credit_account": new_credit,
                            "credit_subaccount": "PayPay",
                            "is_excluded": new_is_ex,
                            "description": new_desc.strip()
                        }
                        rules = [r for r in rules if r["keyword"].lower() != new_kw.strip().lower()]
                        rules.append(new_rule)
                        save_rules(rules)
                        st.success(f"ルールを追加しました: {new_kw}")
                        st.rerun()

            st.divider()
            
            # Rule List Table
            if len(rules) > 0:
                rules_df_list = []
                for i, r in enumerate(rules):
                    rules_df_list.append({
                        "キーワード": r["keyword"],
                        "借方勘定科目": r["debit_account"],
                        "借方税区分": r["debit_tax_class"],
                        "貸方勘定科目": r.get("credit_account", "普通預金"),
                        "除外判定": "除外 (対象外)" if r.get("is_excluded", False) else "対象",
                        "説明": r.get("description", "")
                    })
                st.dataframe(pd.DataFrame(rules_df_list), use_container_width=True, hide_index=True)
                
                # Delete rule selector
                del_col1, del_col2 = st.columns([2, 1])
                with del_col1:
                    rule_to_delete = st.selectbox("削除するルールを選択", [f"{r['keyword']} -> {r['debit_account']}" for r in rules])
                with del_col2:
                    if st.button("🗑️ 選択したルールを削除"):
                        kw_to_del = rule_to_delete.split(" -> ")[0]
                        rules = [r for r in rules if r["keyword"] != kw_to_del]
                        save_rules(rules)
                        st.success(f"ルールを削除しました: {kw_to_del}")
                        st.rerun()
            else:
                st.info("登録されているルールはありません。")

            st.divider()
            
            # Reapply rules to current dataset
            st.subheader("🔄 ルールの再適用 (Re-apply Rules)")
            st.write("設定したルールを現在のデータに再適用します。")
            reapply_col1, reapply_col2 = st.columns(2)
            with reapply_col1:
                overwrite_mode = st.radio(
                    "適用範囲",
                    ["未確認の明細（未編集・未設定）のみに適用", "すべての明細に適用 (これまでの手動変更もリセットされます)"]
                )
            with reapply_col2:
                if st.button("⚡ ルールを再適用する"):
                    paypay_df = load_paypay_csv(selected_file)
                    if paypay_df is not None:
                        fresh_df = apply_categorization_rules(paypay_df, rules, settings)
                        
                        if overwrite_mode == "未確認の明細（未編集・未設定）のみに適用":
                            # Keep manually edited rows or rows that are already modified from '未設定'
                            manual_indices = df[
                                df["is_manually_edited"] | 
                                ((df["借方勘定科目"] != "未設定") & (df["借方勘定科目"].notna()))
                            ]["original_index"].values
                            
                            for idx, row in fresh_df.iterrows():
                                orig_idx = row["original_index"]
                                if orig_idx not in manual_indices:
                                    df.loc[orig_idx] = row
                            st.session_state.df = df
                        else:
                            st.session_state.df = fresh_df
                            st.session_state.wizard_idx = 0
                            
                        st.session_state.df.to_csv(checkpoint_file, encoding="utf-8", index=False)
                        st.success("ルールを再適用し、進捗を保存しました！")
                        st.rerun()

        # ── TAB 3: Reports & Visualizations ──
        with tab_charts:
            st.subheader("📈 収支可視化レポート")
            
            active_df = df[
                (df["対象外"] == False) & 
                (df["借方勘定科目"] != "対象外") & 
                (df["貸方勘定科目"] != "対象外")
            ].copy()
            # Remove "未設定" and "対象外" for charts
            active_df = active_df[(active_df["借方勘定科目"] != "未設定") & (active_df["借方勘定科目"] != "対象外")]
            
            if len(active_df) > 0:
                c_c1, c_c2 = st.columns(2)
                
                with c_c1:
                    # Group by 借方勘定科目 (Expenses)
                    expense_df = active_df.copy()
                    non_expense_accounts = ["普通預金", "現金", "事業主貸"]
                    expense_df = expense_df[expense_df["借方勘定科目"].isin(non_expense_accounts) == False]
                    
                    if len(expense_df) > 0:
                        st.write("📊 経費科目の割合")
                        grp = expense_df.groupby("借方勘定科目")["借方金額(円)"].sum().reset_index()
                        fig = px.pie(
                            grp, 
                            values="借方金額(円)", 
                            names="借方勘定科目", 
                            hole=0.4,
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        fig.update_layout(
                            margin=dict(t=0, b=0, l=0, r=0),
                            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("集計可能な経費データがありません。")
                        
                with c_c2:
                    st.write("📅 月別・勘定科目別の集計")
                    active_df["月"] = active_df["取引日"].apply(lambda x: x[:7] if isinstance(x, str) and len(x) >= 7 else "その他")
                    monthly_grp = active_df.groupby(["月", "借方勘定科目"])["借方金額(円)"].sum().reset_index()
                    
                    fig2 = px.bar(
                        monthly_grp, 
                        x="月", 
                        y="借方金額(円)", 
                        color="借方勘定科目",
                        barmode="stack",
                        color_discrete_sequence=px.colors.qualitative.Safe
                    )
                    fig2.update_layout(
                        margin=dict(t=20, b=20, l=0, r=0),
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                    
                st.divider()
                
                st.write("📋 勘定科目・税区分ごとの集計表")
                summary_table = active_df.groupby(["借方勘定科目", "借方税区分"])["借方金額(円)"].agg(["count", "sum"]).reset_index()
                summary_table.columns = ["勘定科目", "税区分", "件数", "合計金額 (円)"]
                summary_table["合計金額 (円)"] = summary_table["合計金額 (円)"].apply(lambda x: f"¥ {x:,.0f}")
                st.dataframe(summary_table, use_container_width=True, hide_index=True)
            else:
                st.info("仕分け済みの経費取引明細がないため、グラフを表示できません。")
else:
    st.info("👈 左側のサイドバーから、PayPayのCSV取引明細を選択するか、アップロードしてください。")
