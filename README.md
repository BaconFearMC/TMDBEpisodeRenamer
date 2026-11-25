# TMDB Episode Renamer · Browser App

This is a browser-based version of TMDB Episode Renamer for GitHub Pages. Users select video files from their device, search TMDB for a show, load episode metadata, preview filename matches, and download renamed copies in a ZIP.

**Files are processed in the user's browser. Video files are not uploaded to a server, and originals are never modified.** The TMDB API key is entered by the user and kept in page memory only (not stored).

## Publish to GitHub Pages

1. Create a repository.
2. Upload all package contents to the repository root.
3. Go to repository **Settings → Pages**.
4. Under Build and deployment, select **Deploy from a branch**.
5. Choose `main` and `/(root)` and save.
6. Open the published Pages URL.

## Notes / limitations

- Internet connection is required to query TMDB and load the JSZip library (CDN) for ZIP downloads.
- The browser cannot rename or overwrite users' original files directly. This site downloads a ZIP containing renamed copies.
- This is a client-side website. Users provide their own TMDB API key.
- Supported video filename extensions: MKV, MP4, AVI, MOV, WMV, M4V, TS, WEBM, MPG, MPEG.
- Filename matching follows the original script's title similarity behavior and 72% confidence threshold. Files below threshold are marked Review and excluded from the ZIP.
- Folder selection is supported in browsers that implement `webkitdirectory` (Chromium-based browsers).
