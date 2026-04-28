apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Values.applicationName }}-jmx-config
  labels:
    app: {{ .Values.applicationName }}
data:
  jmx-config.yaml: |
    hostPort: localhost:9080
    startDelaySeconds: 10
    ssl: false
    rules:
      - pattern: 'trino.execution<name=QueryManager><>(\w+)'
        name: trino_query_manager_$1
        type: GAUGE
      - pattern: 'trino.execution<name=TaskManager><>(\w+)'
        name: trino_task_manager_$1
        type: GAUGE
      - pattern: 'trino.memory<name=ClusterMemoryManager><>(\w+)'
        name: trino_memory_$1
        type: GAUGE
      - pattern: 'java.lang<type=Memory><HeapMemoryUsage>(\w+)'
        name: jvm_heap_$1
        type: GAUGE
      - pattern: 'java.lang<type=GarbageCollector,name=(.*)><CollectionCount>'
        name: jvm_gc_collection_count
        labels:
          gc: $1
        type: COUNTER