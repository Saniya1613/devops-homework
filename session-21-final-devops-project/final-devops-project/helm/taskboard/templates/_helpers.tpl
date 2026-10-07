{{- define "taskboard.name" -}}{{ default .Release.Name .Values.nameOverride }}{{- end }}
{{- define "taskboard.labels" -}}
app.kubernetes.io/part-of: taskboard
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}
