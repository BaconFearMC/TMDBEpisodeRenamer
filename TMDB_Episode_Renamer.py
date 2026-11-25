import os
import re
import json
import threading
import urllib.parse
import urllib.request
import urllib.error
import difflib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".webm", ".mpg", ".mpeg"}

def request_json(url, api_key):
    url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"api_key": api_key})
    req = urllib.request.Request(url, headers={"User-Agent": "FluxEpisodeRenamer/1.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))

def norm_title(text):
    text = text.lower()
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", text)
    text = re.sub(r"\b(1080p|720p|2160p|480p|web[- ]?dl|web[- ]?rip|bluray|blu[- ]?ray|hdtv|x264|x265|hevc|av1|aac|proper|repack)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())

def parse_filename(path):
    name = os.path.splitext(os.path.basename(path))[0]
    m = re.search(r"(?i)\bS(\d{1,2})\s*E(\d{1,3})\b", name)
    if not m:
        m = re.search(r"(?i)\b(\d{1,2})x(\d{1,3})\b", name)
    season = int(m.group(1)) if m else None
    episode = int(m.group(2)) if m else None
    title = name
    if m:
        title = name[m.end():]
    title = re.sub(r"^[\s._\-]+", "", title)
    title = re.sub(r"(?i)^(?:episode\s*)?\d{1,3}\s*[-._ ]+", "", title)
    return season, episode, title.strip()

class App:
    def __init__(self, root):
        self.root = root
        root.title("TMDB Episode Renamer")
        root.geometry("1080x700")
        root.minsize(850, 560)
        self.api_key = tk.StringVar()
        self.folder = tk.StringVar()
        self.query = tk.StringVar()
        self.show_choice = tk.StringVar()
        self.keep_titles = tk.BooleanVar(value=True)
        self.include_subfolders = tk.BooleanVar(value=True)
        self.results = []
        self.shows = []
        self.episodes = []
        self.files = []
        self.matches = []

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="TMDB API key:").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.api_key, width=46, show="*").grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(top, text="(Your key is used locally and is not saved)").grid(row=0, column=2, sticky="w")
        top.columnconfigure(1, weight=1)

        search = ttk.LabelFrame(root, text="1. Find the show on TMDB", padding=10)
        search.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Entry(search, textvariable=self.query).pack(side="left", fill="x", expand=True)
        ttk.Button(search, text="Search TMDB", command=self.search_show).pack(side="left", padx=6)
        self.show_combo = ttk.Combobox(search, textvariable=self.show_choice, state="readonly", width=65)
        self.show_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(search, text="Load Episodes", command=self.load_show).pack(side="left", padx=6)

        folder_frame = ttk.LabelFrame(root, text="2. Choose your media folder", padding=10)
        folder_frame.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Entry(folder_frame, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        ttk.Button(folder_frame, text="Browse...", command=self.browse).pack(side="left", padx=6)
        ttk.Button(folder_frame, text="Scan & Match", command=self.scan_match).pack(side="left")

        opts = ttk.Frame(root, padding=(10, 0, 10, 8))
        opts.pack(fill="x")
        ttk.Checkbutton(opts, text="Include subfolders", variable=self.include_subfolders).pack(side="left")
        ttk.Checkbutton(opts, text="Include TMDB episode titles in renamed files", variable=self.keep_titles).pack(side="left", padx=15)

        table_frame = ttk.Frame(root, padding=10)
        table_frame.pack(fill="both", expand=True)
        cols = ("status", "current", "proposed", "match")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("status", text="Status")
        self.tree.heading("current", text="Current filename")
        self.tree.heading("proposed", text="Proposed filename")
        self.tree.heading("match", text="TMDB match")
        self.tree.column("status", width=110, stretch=False)
        self.tree.column("current", width=300)
        self.tree.column("proposed", width=300)
        self.tree.column("match", width=260)
        vs = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        bottom = ttk.Frame(root, padding=10)
        bottom.pack(fill="x")
        self.status = ttk.Label(bottom, text="Enter your TMDB API key, search for a show, choose a folder, then scan.")
        self.status.pack(side="left", fill="x", expand=True)
        ttk.Button(bottom, text="Rename Approved Matches", command=self.apply_renames).pack(side="right")
        ttk.Button(bottom, text="Clear Preview", command=self.clear).pack(side="right", padx=6)

    def browse(self):
        p = filedialog.askdirectory()
        if p:
            self.folder.set(p)

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self.matches = []
        self.status.config(text="Preview cleared.")

    def validate_key(self):
        if not self.api_key.get().strip():
            messagebox.showerror("API key needed", "Enter your TMDB API key first.")
            return False
        return True

    def search_show(self):
        if not self.validate_key():
            return
        q = self.query.get().strip()
        if not q:
            messagebox.showinfo("Search", "Enter a show name.")
            return
        self.status.config(text="Searching TMDB...")
        def work():
            try:
                data = request_json("https://api.themoviedb.org/3/search/tv?query=" + urllib.parse.quote(q), self.api_key.get().strip())
                shows = data.get("results", [])
                self.root.after(0, lambda: self.search_done(shows))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("TMDB error", str(e)))
                self.root.after(0, lambda: self.status.config(text="Search failed."))
        threading.Thread(target=work, daemon=True).start()

    def search_done(self, shows):
        self.shows = shows
        options = []
        for s in shows:
            year = (s.get("first_air_date") or "")[:4]
            options.append(f'{s.get("name", "?")} ({year})  |  TMDB ID {s.get("id")}')
        self.show_combo["values"] = options
        if options:
            self.show_combo.current(0)
            self.status.config(text=f"Found {len(options)} show result(s). Select the correct one.")
        else:
            self.status.config(text="No shows found.")

    def load_show(self):
        if not self.shows or self.show_combo.current() < 0:
            messagebox.showinfo("Select show", "Search and select a show first.")
            return
        show = self.shows[self.show_combo.current()]
        self.status.config(text=f'Loading episodes for {show.get("name")}...')
        def work():
            try:
                detail = request_json(f"https://api.themoviedb.org/3/tv/{show['id']}", self.api_key.get().strip())
                eps = []
                for season in detail.get("seasons", []):
                    sn = season.get("season_number", 0)
                    if sn < 0:
                        continue
                    season_data = request_json(f"https://api.themoviedb.org/3/tv/{show['id']}/season/{sn}", self.api_key.get().strip())
                    for ep in season_data.get("episodes", []):
                        eps.append({
                            "season": int(ep.get("season_number", sn)),
                            "episode": int(ep.get("episode_number", 0)),
                            "title": ep.get("name", ""),
                            "id": ep.get("id"),
                        })
                self.root.after(0, lambda: self.load_done(show, eps))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("TMDB error", str(e)))
                self.root.after(0, lambda: self.status.config(text="Episode loading failed."))
        threading.Thread(target=work, daemon=True).start()

    def load_done(self, show, eps):
        self.episodes = eps
        self.show = show
        self.status.config(text=f'Loaded {len(eps)} episodes for {show.get("name")}. Choose the folder and scan.')

    def scan_match(self):
        try:
            if not self.episodes:
                messagebox.showinfo("No episode list", "Search for a show and click Load Episodes first.")
                return

            folder = self.folder.get().strip()
            if not folder or not os.path.isdir(folder):
                messagebox.showerror("Folder", "Choose a valid folder.")
                return

            self.tree.delete(*self.tree.get_children())
            self.matches = []
            self.files = []
            self.status.config(text="Scanning files...")
            self.root.update_idletasks()

            # Find video files
            if self.include_subfolders.get():
                for base, _, names in os.walk(folder):
                    for name in names:
                        if os.path.splitext(name)[1].lower() in VIDEO_EXTS:
                            self.files.append(os.path.join(base, name))
            else:
                for name in os.listdir(folder):
                    path = os.path.join(folder, name)
                    if os.path.isfile(path) and os.path.splitext(name)[1].lower() in VIDEO_EXTS:
                        self.files.append(path)

            self.files.sort()
            used = set()
            rows = []

            total = len(self.files)

            for index, path in enumerate(self.files, start=1):
                if index % 10 == 0:
                    self.status.config(text=f"Matching files... {index}/{total}")
                    self.root.update_idletasks()

                src_s, src_e, title = parse_filename(path)
                ntitle = norm_title(title)

                best = None
                score = 0

                # Match filename title against TMDB episode titles
                if ntitle:
                    for ep in self.episodes:
                        candidate = norm_title(ep["title"])

                        if not candidate:
                            continue

                        if (ep["season"], ep["episode"]) in used:
                            continue

                        ratio = difflib.SequenceMatcher(
                            None, ntitle, candidate
                        ).ratio()

                        if ntitle == candidate:
                            ratio = 1.0

                        if candidate in ntitle or ntitle in candidate:
                            ratio = max(
                                ratio,
                                min(len(candidate), len(ntitle))
                                / max(len(candidate), len(ntitle))
                            )

                        if ratio > score:
                            score = ratio
                            best = ep

                status = "Matched" if best and score >= 0.72 else "Review"
                proposed = ""
                match_text = ""

                if status == "Matched":
                    used.add((best["season"], best["episode"]))
                    ext = os.path.splitext(path)[1]

                    if self.keep_titles.get():
                        filename = (
                            f'{self.show.get("name")} - '
                            f'S{best["season"]:02d}E{best["episode"]:02d} - '
                            f'{best["title"]}'
                        )
                    else:
                        filename = (
                            f'{self.show.get("name")} - '
                            f'S{best["season"]:02d}E{best["episode"]:02d}'
                        )

                    # Sanitize invalid Windows filename characters
                    filename = re.sub(r'[<>:"/\\|?*]', "-", filename)
                    filename = re.sub(r'[\x00-\x1f]', "", filename)
                    filename = filename.rstrip(" .")

                    proposed = filename + ext

                    match_text = (
                        f'S{best["season"]:02d}E{best["episode"]:02d} '
                        f'{best["title"]} ({score:.0%})'
                    )

                else:
                    if src_s is not None:
                        match_text = (
                            f"Filename number S{src_s:02d}E{src_e:02d}; "
                            "title not confident"
                        )
                    else:
                        match_text = "No episode title/number detected"

                self.matches.append({
                    "path": path,
                    "proposed": proposed,
                    "status": status,
                    "episode": best if status == "Matched" else None
                })

                rows.append((
                    status,
                    os.path.relpath(path, folder),
                    proposed,
                    match_text
                ))

            # Populate preview after matching is finished
            for row in rows:
                self.tree.insert("", "end", values=row)

            matched = sum(
                1 for m in self.matches
                if m["status"] == "Matched"
            )

            self.status.config(
                text=f"Scanned {total} video file(s). "
                     f"{matched} confident title match(es); "
                     f"{total - matched} need review."
            )

        except Exception as e:
            self.status.config(text="Scan failed!")
            messagebox.showerror(
                "Scan Error",
                f"Something went wrong while scanning:\n\n{type(e).__name__}: {e}"
            )

    def apply_renames(self):
        approved = [m for m in self.matches if m["status"] == "Matched" and m["proposed"]]
        if not approved:
            messagebox.showinfo("Nothing to rename", "No confident matches are available to rename.")
            return
        if not messagebox.askyesno(
            "Confirm rename",
            f"Rename {len(approved)} matched file(s)?\n\n"
            "Close Flux and stop your torrent client first. Unmatched files will not be changed."
        ):
            return

        staged = []
        try:
            # Stage through temporary names so renames cannot collide with each other.
            for m in approved:
                old = m["path"]
                new = os.path.join(os.path.dirname(old), m["proposed"])
                if old == new:
                    continue
                if os.path.exists(new) and new not in [x["path"] for x in approved]:
                    raise FileExistsError(f"Destination already exists:\n{new}")
                temp = old + ".__tmdb_renamer_tmp__"
                if os.path.exists(temp):
                    raise FileExistsError(f"Temporary path already exists:\n{temp}")
                os.rename(old, temp)
                staged.append((temp, new, old))

            for temp, new, old in staged:
                os.rename(temp, new)

            messagebox.showinfo("Complete", f"Renamed {len(staged)} file(s).")
            self.scan_match()
        except Exception as e:
            # Attempt to restore every file already staged/renamed.
            restore_errors = []
            for temp, new, old in reversed(staged):
                try:
                    if os.path.exists(temp):
                        os.rename(temp, old)
                    elif os.path.exists(new) and not os.path.exists(old):
                        os.rename(new, old)
                except Exception as restore_error:
                    restore_errors.append(f"{old}\n{restore_error}")

            if getattr(e, "winerror", None) == 32 or "being used by another process" in str(e).lower():
                message = (
                    "Windows says one or more files are currently in use.\n\n"
                    "Stop the torrent completely (not just pause), close Flux, and close any "
                    "video player or Explorer preview using the folder. Then scan again and retry.\n\n"
                    f"File/error:\n{e}"
                )
            else:
                message = f"Rename failed:\n{e}"

            if restore_errors:
                message += "\n\nSome files could not be restored automatically:\n" + "\n\n".join(restore_errors)
            messagebox.showerror("Rename error", message)

if __name__ == "__main__":
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
