# Third-party notices

laiive is proprietary (see [LICENSE](LICENSE)). It is built on open-source components that keep
their own licences. None of them is copyleft in a way that binds laiive's own code.

## Shipped to the browser (frontend bundle)

| Component | Licence |
| --- | --- |
| react, react-dom, react-router-dom | MIT |
| @supabase/supabase-js | MIT |
| @tanstack/react-query | MIT |
| sonner, clsx, tailwind-merge | MIT |
| dompurify | Apache-2.0 (dual MPL-2.0 / Apache-2.0; used under Apache-2.0) |

The full licence text of each is in its package under `node_modules/`.

## Server side (not distributed)

Python services: FastAPI, the neo4j driver (Apache-2.0), OpenAI, httpx, Prefect, redis,
OpenTelemetry and arize-phoenix-otel / openinference (Apache-2.0, tracing client only),
pypdf, python-docx and others, all under permissive licences. certifi and tqdm are MPL-2.0 and
used unmodified. text-unidecode (dev-only, not in any image) is used under the Artistic licence.

## Data and fonts

- **Map data and geocoding** © [OpenStreetMap](https://www.openstreetmap.org/copyright)
  contributors, under the Open Database License (ODbL). Timezone data (timezonefinder) derives
  from OpenStreetMap too.
- **Fonts:** Bebas Neue, DM Sans and IBM Plex Mono, SIL Open Font License 1.1, served by Google
  Fonts.
