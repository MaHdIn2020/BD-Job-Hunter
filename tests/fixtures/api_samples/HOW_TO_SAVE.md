# Save real API responses (do this yourself, 2 minutes)

The IDE cannot reach these APIs from its sandbox, so save the files by hand.
Use them in tests with `respx`. Never call the live APIs in default tests.

## Jobicy -> save as `jobicy_sample.json`
Open in a browser, then Ctrl+S (or copy all text into a new file):

    https://jobicy.com/api/v2/remote-jobs?count=20&tag=python

- Top-level key `jobs` holds the listings.
- Titles may be HTML-entity encoded (for example `&amp;#8211;`). Tests must check decoding.
- Keep the original `url` of each job. Credit Jobicy in the UI.
- Call at most once per hour while developing.

## RemoteOK -> save as `remoteok_sample.json`
Open in a browser and save the text:

    https://remoteok.com/api

- The first array item is a legal notice, not a job. Tests must check it is skipped.
- Keep the original listing URL. Credit RemoteOK in the UI.

## After saving
Files go in `tests/fixtures/api_samples/`. If a sample contains anything personal, delete that field.
