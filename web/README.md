# Scrubbed — coordinator dashboard

The command centre and permanent record for the perioperative team: the case board,
each case's detail (team, patient, pre-op checklist, balance and the instrument
second-count audit), the paging ladder, the conversations, the uploaded forms and the
post-op follow-up queue.

React + Vite + TypeScript. React Query for data, a thin Cognito client for auth (no AWS
SDK in the bundle), HashRouter so deep links work on S3 and CloudFront.

## Run the demo (no API, no login needed)

```
npm install
VITE_DEMO=1 npm run dev
```

Open the printed URL and click "Open the demo". The app runs on seeded theatre data for
today: cases across two theatres, one case at risk, one with an instrument discrepancy
flagged, a paging ladder with mixed read and acknowledged states, conversations, uploaded
forms and a follow-up queue.

## Build

```
npm install
npm run build        # tsc -b && vite build, output in dist/
```

## Against the live API

Copy `.env.example` to `.env.local` and set `VITE_API_URL`, `VITE_COGNITO_REGION` and
`VITE_COGNITO_CLIENT_ID` (leave `VITE_DEMO=0`). The Cognito app client needs
`USER_PASSWORD_AUTH` and `REFRESH_TOKEN_AUTH` enabled.

## API the dashboard calls

`GET /me`, `GET /cases?day=`, `GET /cases/{id}`, `GET /cases/{id}/pages`,
`GET /cases/{id}/conversations`, `GET /cases/{id}/forms`, `GET /followups`, `GET /staff`,
`POST /cases`, `PATCH /cases/{id}`, `POST /cases/{id}/page`, `POST /staff`.
