{{- define "careslot.name" -}}{{ default .Release.Name .Values.nameOverride | trunc 50 | trimSuffix "-" }}{{- end }}

{{- define "careslot.labels" -}}
app.kubernetes.io/part-of: careslot
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}
