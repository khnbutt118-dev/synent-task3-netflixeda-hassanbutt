"""Synent Data Science Internship - Task 3: Exploratory Data Analysis (Netflix)
Author: Hassan Butt
Run: python main.py
"""

import sys, os, re, json, shutil, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")


DATASETS = {'netflix': {'files': ['netflix_titles.csv'],
             'kaggle': 'shivamb/netflix-shows',
             'name': 'Netflix Movies and TV Shows',
             'page': 'https://www.kaggle.com/datasets/shivamb/netflix-shows'}}



def _outdir(repo_dir):
    p = Path(repo_dir) / "outputs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_fig(fig, repo_dir, name):
    fig.savefig(_outdir(repo_dir) / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return name


def save_json(obj, repo_dir, name):
    (_outdir(repo_dir) / name).write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _read_csv(path, spec):
    kw = {"encoding": spec.get("encoding", "utf-8")}
    if spec.get("no_header_file") and Path(path).name == spec["no_header_file"]:
        kw["header"] = None
        kw["names"] = spec["names"]
    try:
        return pd.read_csv(path, **kw)
    except UnicodeDecodeError:
        kw["encoding"] = "latin-1"
        return pd.read_csv(path, **kw)


def _builtin(key):
    if key == "iris":
        from sklearn.datasets import load_iris
        d = load_iris(as_frame=True)
        df = d.frame.drop(columns=["target"])
        df["species"] = [d.target_names[i] for i in d.target]
        return df
    raise KeyError(key)


def get_data(key, repo_dir):
    """Load a dataset: local data/ folder -> built-in -> kagglehub -> public URL."""
    spec = DATASETS[key]
    data_dir = Path(repo_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in spec["files"]:
        p = data_dir / name
        if p.exists():
            print(f"  [data] using local file {p}")
            return _read_csv(p, spec)
    if spec.get("builtin"):
        print("  [data] using built-in copy")
        return _builtin(key)
    if spec.get("kaggle"):
        try:
            import kagglehub
            folder = Path(kagglehub.dataset_download(spec["kaggle"]))
            cands = list(folder.rglob("*.csv"))
            pick = None
            for want in spec["files"]:
                for c in cands:
                    if c.name.lower() == want.lower():
                        pick = c
                        break
                if pick:
                    break
            if pick is None and cands:
                pick = cands[0]
            if pick is not None:
                dest = data_dir / pick.name
                shutil.copy(pick, dest)
                print(f"  [data] downloaded from Kaggle: {dest}")
                return _read_csv(dest, spec)
        except Exception as e:
            print(f"  [data] kagglehub download not available ({type(e).__name__}: {e})")
    if spec.get("url"):
        try:
            import urllib.request
            dest = data_dir / (spec.get("no_header_file") or spec["files"][0])
            urllib.request.urlretrieve(spec["url"], dest)
            print(f"  [data] downloaded from public URL: {dest}")
            return _read_csv(dest, spec)
        except Exception as e:
            print(f"  [data] public URL download failed ({type(e).__name__}: {e})")
    raise FileNotFoundError(
        f"Dataset '{spec['name']}' not found.\n"
        f"  -> Download it from {spec['page']}\n"
        f"  -> Save the CSV as one of {spec['files']} inside: {data_dir.resolve()}\n"
        f"  -> Then run the script again.")


def _to_datetime(series):
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except (ValueError, TypeError):
        return pd.to_datetime(series, errors="coerce")


def _snake(col):
    return re.sub(r"[^0-9a-zA-Z]+", "_", str(col).strip()).strip("_").lower()


def task3_run(repo_dir):
    df = get_data("netflix", repo_dir)
    df.columns = [_snake(c) for c in df.columns]
    shape = [int(df.shape[0]), int(df.shape[1])]
    df["date_added"] = _to_datetime(df["date_added"].astype("string").str.strip())
    df["year_added"] = df["date_added"].dt.year
    df["month_added"] = df["date_added"].dt.month
    df["duration_value"] = pd.to_numeric(df["duration"].astype("string").str.extract(r"(\d+)", expand=False), errors="coerce")
    df["lag_years"] = df["year_added"] - df["release_year"]
    movies = df[df["type"] == "Movie"].copy()
    tv = df[df["type"] == "TV Show"].copy()

    # Summary statistics
    summary = df[["release_year", "year_added", "month_added", "lag_years"]].describe().round(2)
    summary.to_csv(_outdir(repo_dir) / "summary_statistics.csv")
    missing_pct = (df.isna().mean() * 100).round(1).sort_values(ascending=False)
    missing_pct.to_csv(_outdir(repo_dir) / "missing_values_percent.csv")

    # Trend 1: titles added per year by type
    per_year = df.dropna(subset=["year_added"]).groupby(["year_added", "type"]).size().unstack(fill_value=0)
    per_year.index = per_year.index.astype(int)
    fig, ax = plt.subplots(figsize=(10, 5))
    per_year.plot(ax=ax, marker="o")
    ax.set_title("Trend: titles added to Netflix per year")
    ax.set_xlabel("Year added")
    ax.set_ylabel("Number of titles")
    save_fig(fig, repo_dir, "trend_titles_added_per_year.png")

    # Type split + ratings
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    df["type"].value_counts().plot(kind="bar", ax=ax[0], color=["#e74c3c", "#34495e"])
    ax[0].set_title("Movies vs TV Shows")
    ax[0].tick_params(axis="x", rotation=0)
    df["rating"].value_counts().head(10).plot(kind="barh", ax=ax[1], color="#2980b9")
    ax[1].set_title("Top 10 content ratings")
    ax[1].invert_yaxis()
    save_fig(fig, repo_dir, "type_and_ratings.png")

    # Countries and genres
    countries = df["country"].dropna().astype(str).str.split(",").explode().str.strip()
    countries = countries[countries != ""]
    genres = df["listed_in"].dropna().astype(str).str.split(",").explode().str.strip()
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    countries.value_counts().head(10).plot(kind="barh", ax=ax[0], color="#16a085")
    ax[0].set_title("Top 10 producing countries")
    ax[0].invert_yaxis()
    genres.value_counts().head(10).plot(kind="barh", ax=ax[1], color="#8e44ad")
    ax[1].set_title("Top 10 genres")
    ax[1].invert_yaxis()
    fig.tight_layout()
    save_fig(fig, repo_dir, "top_countries_and_genres.png")

    # Movie duration trend
    movies = movies.dropna(subset=["duration_value"])
    movies["decade"] = (movies["release_year"] // 10 * 10).astype(int)
    dur_decade = movies.groupby("decade")["duration_value"].mean()
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    sns.histplot(movies["duration_value"], bins=40, ax=ax[0], color="#e67e22")
    ax[0].set_title("Movie duration distribution (minutes)")
    dur_decade.plot(ax=ax[1], marker="o", color="#c0392b")
    ax[1].set_title("Average movie duration by release decade")
    ax[1].set_ylabel("minutes")
    save_fig(fig, repo_dir, "movie_duration_trends.png")

    # Correlation analysis
    num_cols = ["release_year", "year_added", "month_added", "duration_value"]
    corr_movies = movies[num_cols].corr().round(2)
    corr_movies.to_csv(_outdir(repo_dir) / "correlation_movies.csv")
    fig, ax = plt.subplots(figsize=(6.5, 5))
    sns.heatmap(corr_movies, annot=True, cmap="coolwarm", vmin=-1, vmax=1, ax=ax)
    ax.set_title("Correlation (movies): release year, year added, month added, duration")
    save_fig(fig, repo_dir, "correlation_heatmap_movies.png")

    # Lag between release and addition
    fig, ax = plt.subplots(figsize=(9, 4.5))
    lag = df["lag_years"].dropna()
    lag = lag[(lag >= 0) & (lag <= 20)]
    sns.histplot(lag, bins=21, ax=ax, color="#2c3e50")
    ax.set_title("Years between release and being added to Netflix")
    save_fig(fig, repo_dir, "release_to_added_lag.png")

    peak_year = int(per_year.sum(axis=1).idxmax())
    movie_share = float((df["type"] == "Movie").mean() * 100)
    top_country = countries.value_counts().index[0]
    top_genre = genres.value_counts().index[0]
    corr_rel_add = float(corr_movies.loc["release_year", "year_added"])
    corr_rel_dur = float(corr_movies.loc["release_year", "duration_value"])
    median_dur = float(movies["duration_value"].median())
    median_lag = float(df["lag_years"].dropna().median())
    peak_count = int(per_year.sum(axis=1).max())
    insights = [
        f"Netflix added the most titles in {peak_year} ({peak_count:,} titles) of all the years in the data.",
        f"Movies make up {movie_share:.0f}% of the catalogue and TV shows {100 - movie_share:.0f}%.",
        f"The most common producing country is {top_country} and the most common genre label is '{top_genre}'.",
        f"The median movie runs {median_dur:.0f} minutes; correlation between release year and duration is {corr_rel_dur:.2f}.",
        f"The median gap between a title's release and its addition to Netflix is {median_lag:.0f} year(s); release year and year added correlate at r = {corr_rel_add:.2f} for movies.",
    ]
    return {"headline": {"Titles analysed": shape[0], "Peak year for additions": peak_year,
                         "Movie share": f"{movie_share:.0f}%", "Top country": top_country,
                         "Median movie duration (min)": round(median_dur)},
            "insights": insights, "dataset_shape": shape,
            "files": ["trend_titles_added_per_year.png", "type_and_ratings.png", "top_countries_and_genres.png",
                      "movie_duration_trends.png", "correlation_heatmap_movies.png", "release_to_added_lag.png",
                      "summary_statistics.csv", "correlation_movies.csv", "missing_values_percent.csv"]}



if __name__ == "__main__":
    res = task3_run(Path(__file__).parent)
    print(json.dumps(res, indent=2, default=str))
