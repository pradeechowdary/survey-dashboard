import streamlit as st
import pandas as pd
import plotly.express as px

# ==============================
# CONFIG
# ==============================
SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "13UyKNgOm4h8-kdZg0uhKa6YlFDCceHfEmY5qzN1x2Qc/export?format=csv&gid=0"
)

# mapping from raw metric codes in sheet -> nice labels for UI
METRIC_LABELS = {
    "act": "Liked / Likely to Act",
    "mot": "Motivating",
    "trust": "Trustworthy",
}
INV_METRIC_LABELS = {v: k for k, v in METRIC_LABELS.items()}

st.set_page_config(
    page_title="Message Evaluation Survey Dashboard",
    layout="wide",
)


# ==============================
# DATA LOADER
# ==============================
@st.cache_data(ttl=60)  # cache for 60 seconds, auto-refresh after
def load_data():
    df = pd.read_csv(SHEET_CSV_URL)

    # normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    # timestamp to datetime if present
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # numeric rating column
    if "value" in df.columns:
        df["value_num"] = pd.to_numeric(df["value"], errors="coerce")
    else:
        df["value_num"] = None

    return df


# ==============================
# MAIN APP
# ==============================
st.title("📊 Message Evaluation Survey Dashboard")
st.caption("Data source: live Google Sheet (auto-updates, cached for 60 seconds).")

df = load_data()

# quick KPIs at top
col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
col_kpi1.metric("Total Responses (rows)", len(df))
col_kpi2.metric("Unique Participants", df["session_id"].nunique())
col_kpi3.metric(
    "Images with Ratings",
    df[df["type"] == "rating"]["image_name"].nunique()
)

# create tabs
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🖼 Image Ratings",
        "🆚 Comparisons",
        "❓ General Questions",
        "💬 Feedback",
    ]
)

# ---------------------------------------------------
# TAB 1: IMAGE RATINGS
# ---------------------------------------------------
with tab1:
    st.subheader("Image Ratings (1–5)")

    ratings_df = df[df["type"] == "rating"].copy()

    if ratings_df.empty:
        st.warning("No rating data found yet.")
    else:

        # Metric selector only (act / mot / trust)
        raw_metrics = ratings_df["metric"].dropna().unique().tolist()
        metric_options = [METRIC_LABELS[m] for m in raw_metrics if m in METRIC_LABELS]

        selected_metric_label = st.selectbox(
            "Rating type:",
            options=sorted(metric_options),
            index=0,
        )
        selected_metric = INV_METRIC_LABELS[selected_metric_label]

        # IMAGE TABS
        image_options = sorted(
            ratings_df["image_name"].dropna().unique().tolist()
        )

        img_tabs = st.tabs(image_options)

        for i, img_name in enumerate(image_options):
            with img_tabs[i]:

                filt = (
                    (ratings_df["metric"] == selected_metric) &
                    (ratings_df["image_name"] == img_name)
                )
                img_metric_df = ratings_df[filt].copy()

                if img_metric_df.empty:
                    st.warning("No ratings yet for this image.")
                else:
                    st.markdown(f"### {selected_metric_label}")

                    col_a, col_b = st.columns(2)

                    # -----------------------------
                    # Per-user bar (centered height, no weird ticks)
                    # -----------------------------
                    with col_a:
                        per_user_df = (
                            img_metric_df[["session_id", "value_num"]]
                            .dropna()
                            .groupby("session_id", as_index=False)
                            .mean()
                        )

                        fig_user = px.bar(
                            per_user_df,
                            x="session_id",
                            y="value_num",
                            labels={
                                "session_id": "Participant",
                                "value_num": "Rating (1–5)"
                            }
                        )
                        fig_user.update_traces(width=0.4, marker_color="#4f46e5")
                        fig_user.update_yaxes(range=[1, 5], dtick=1)   # FIXED
                        fig_user.update_layout(
                            height=380,
                            bargap=0.35,
                            title=None,
                        )
                        st.plotly_chart(fig_user, use_container_width=True)

                    # -----------------------------
                    # Rating distribution
                    # -----------------------------
                    with col_b:
                        dist_df = (
                            img_metric_df[["value_num"]]
                            .dropna()
                            .value_counts()
                            .reset_index(name="count")
                            .rename(columns={"value_num": "rating"})
                            .sort_values("rating")
                        )

                        st.markdown("**Rating distribution (count of 1–5)**")

                        fig_dist = px.bar(
                            dist_df,
                            x="rating",
                            y="count",
                            labels={
                                "rating": "Rating (1–5)",
                                "count": "Responses"
                            },
                        )
                        fig_dist.update_traces(width=0.4, marker_color="#22c55e")

                        # FORCE AXES TO BE CLEAN
                        fig_dist.update_xaxes(dtick=1)
                        fig_dist.update_yaxes(dtick=1)

                        fig_dist.update_layout(
                            height=380,
                            bargap=0.35,
                            title=None,
                        )
                        st.plotly_chart(fig_dist, use_container_width=True)

# ---------------------------------------------------
# TAB 2: COMPARISONS
# ---------------------------------------------------
with tab2:
    st.subheader("Comparisons")

    # mapping ab1 → image names
    COMPARISON_LABELS = {
        "ab1": "img1 vs img4",
        "ab2": "img11 vs img14",
        "ab3": "img16 vs img7",
        "ab4": "img21 vs img9",
    }

    ab_df = df[df["type"] == "ab"].copy()

    if ab_df.empty:
        st.warning("No comparison data yet.")
    else:
        # list of raw keys: ab1, ab2...
        comp_options = (
            ab_df["image_name"]
            .dropna()
            .unique()
            .tolist()
        )

        # convert raw keys → pretty titles
        pretty_options = [
            COMPARISON_LABELS.get(x, x) for x in comp_options
        ]

        # show pretty label, but keep raw key using mapping
        selected_pretty = st.selectbox(
            "Choose comparison:",
            options=pretty_options,
            index=0
        )

        # find raw key from pretty label
        selected_comp = (
            [k for k, v in COMPARISON_LABELS.items() if v == selected_pretty][0]
        )

        this_ab = ab_df[ab_df["image_name"] == selected_comp].copy()
        this_ab["choice"] = this_ab["value"]

        summary = this_ab["choice"].value_counts().reset_index()
        summary.columns = ["choice", "count"]

        st.markdown(f"### Results for **{selected_pretty}**")

        fig_ab = px.bar(
            summary,
            x="choice",
            y="count",
            labels={
                "choice": "Choice (A / B / Neither)",
                "count": "Number of responses",
            },
        )
        fig_ab.update_traces(width=0.4, marker_color="#f97316")
        fig_ab.update_layout(bargap=0.35, height=420)
        st.plotly_chart(fig_ab, use_container_width=True)

        with st.expander("Raw comparison responses"):
            st.dataframe(
                this_ab[["timestamp", "session_id", "image_name", "value"]],
                use_container_width=True,
            )

# ---------------------------------------------------
# TAB 3: GENERAL QUESTIONS
# ---------------------------------------------------
with tab3:
    st.subheader("General Questions")

    gen_df = df[df["type"] == "general"].copy()

    if gen_df.empty:
        st.warning("No general-question data yet.")
    else:
        col1, col2, col3 = st.columns(3)

        # 1) Which type motivates most
        with col1:
            motiv_df = gen_df[gen_df["image_name"] == "motivatesMost"].copy()
            if not motiv_df.empty:
                summary = motiv_df["value"].value_counts().reset_index()
                summary.columns = ["option", "count"]
                st.markdown("**What motivates people most?**")
                fig = px.pie(
                    summary,
                    names="option",
                    values="count",
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data yet for ‘motivatesMost’.")

        # 2) Which type would they ignore
        with col2:
            ignore_df = gen_df[gen_df["image_name"] == "ignore"].copy()
            if not ignore_df.empty:
                summary = ignore_df["value"].value_counts().reset_index()
                summary.columns = ["option", "count"]
                st.markdown("**Which messages do people tend to ignore?**")
                fig = px.bar(
                    summary,
                    x="option",
                    y="count",
                    labels={"option": "Option", "count": "Responses"},
                )
                fig.update_traces(marker_color="#e11d48", width=0.45)
                fig.update_layout(
                    xaxis_tickangle=-35,
                    bargap=0.35,
                    height=420,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data yet for ‘ignore’.")

        # 3) Frequency preference
        with col3:
            freq_df = gen_df[gen_df["image_name"] == "frequency"].copy()
            if not freq_df.empty:
                summary = freq_df["value"].value_counts().reset_index()
                summary.columns = ["option", "count"]
                st.markdown("**Preferred number of messages per week**")
                fig = px.pie(
                    summary,
                    names="option",
                    values="count",
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data yet for ‘frequency’.")

# ---------------------------------------------------
# TAB 4: FEEDBACK
# ---------------------------------------------------
with tab4:
    st.subheader("Open Feedback")

    fb_df = df[df["type"] == "feedback"].copy()
    if fb_df.empty:
        st.info("No feedback submitted yet.")
    else:
        fb_df = fb_df.rename(columns={"value": "feedback_text"})
        st.dataframe(
            fb_df[["timestamp", "session_id", "feedback_text"]],
            use_container_width=True,
        )
