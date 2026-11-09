{{- define "jobbot.appEnv" -}}
- name: POSTGRES_PASSWORD
  valueFrom: {secretKeyRef: {name: {{ .Values.existingSecret }}, key: POSTGRES_PASSWORD}}
- name: DATABASE_URL                          # $(VAR) expands the env var defined above
  value: "postgresql+asyncpg://jobbot:$(POSTGRES_PASSWORD)@db:5432/jobbot"
- name: JWT_SECRET_KEY
  valueFrom: {secretKeyRef: {name: {{ .Values.existingSecret }}, key: JWT_SECRET_KEY}}
- name: SMTP_USER
  valueFrom: {secretKeyRef: {name: {{ .Values.existingSecret }}, key: SMTP_USER, optional: true}}
- name: SMTP_PASSWORD
  valueFrom: {secretKeyRef: {name: {{ .Values.existingSecret }}, key: SMTP_PASSWORD, optional: true}}
- name: EMAIL_FROM
  valueFrom: {secretKeyRef: {name: {{ .Values.existingSecret }}, key: EMAIL_FROM, optional: true}}
- name: COOKIE_SECURE
  value: {{ .Values.app.cookieSecure | quote }}
- name: TRUST_CF_CONNECTING_IP
  value: {{ .Values.app.trustCfConnectingIp | quote }}
- name: DOCS_ENABLED
  value: {{ .Values.app.docsEnabled | quote }}
{{- end }}

{{- define "jobbot.hardened" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
runAsNonRoot: true
capabilities: {drop: ["ALL"]}
{{- end }}

{{- define "jobbot.apiImage" -}}
"{{ .Values.image.api }}:{{ .Values.image.tag }}"
{{- end }}
