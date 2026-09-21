{{/*
Chart name, release-qualified fullname, and shared labels.
*/}}
{{- define "oap.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "oap.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "oap.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Labels every object carries. */}}
{{- define "oap.labels" -}}
helm.sh/chart: {{ include "oap.chart" . }}
app.kubernetes.io/name: {{ include "oap.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: onchain-agent-platform
{{- end -}}

{{/*
Selector labels for one component. Usage: include "oap.selectorLabels" (dict "root" . "component" "agent")
Selectors are immutable on Deployments, so keep this set small and stable.
*/}}
{{- define "oap.selectorLabels" -}}
app.kubernetes.io/name: {{ include "oap.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Per-component resource name, e.g. <release>-onchain-agent-platform-agent */}}
{{- define "oap.componentName" -}}
{{- printf "%s-%s" (include "oap.fullname" .root) .component | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "oap.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "oap.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/* Name of the Secret the pods read: chart-managed or user-provided. */}}
{{- define "oap.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- include "oap.fullname" . -}}
{{- end -}}
{{- end -}}

{{/* Pod security defaults for the images this repository builds (uid 10001). */}}
{{- define "oap.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
fsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "oap.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}
