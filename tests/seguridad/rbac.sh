#!/usr/bin/env bash
# E09: denegación por RBAC de Kubernetes (con la identidad evaluada) y por permisos de usuarios de BD.
set -uo pipefail
R=$(cd "$(dirname "$0")/../.." && pwd); K="kubectl --context k3d-ra-prod -n redalimenta"
echo "# $(date -u +%FT%TZ)"
for u in ana.operadora luis.lector; do
  KC="$R/secrets/usuarios/$u-prod.kubeconfig"; echo "== Identidad: $(kubectl --kubeconfig $KC auth whoami -o jsonpath='{.status.userInfo.username} grupos={.status.userInfo.groups}')"
  for t in "get pods" "list deployments" "get secrets" "patch deployments" "delete pods" "create pods/exec" "delete statefulsets" "create jobs"; do
    printf "  %-32s %s\n" "$t" "$(kubectl --kubeconfig $KC auth can-i $t -n redalimenta 2>/dev/null)"; done
  printf "  %-32s %s\n" "get pods (ns kube-system)" "$(kubectl --kubeconfig $KC auth can-i get pods -n kube-system 2>/dev/null)"
  printf "  %-32s %s\n" "create clusterrolebindings" "$(kubectl --kubeconfig $KC auth can-i create clusterrolebindings 2>/dev/null)"
done
echo "== Acción real denegada (lector intenta leer un Secret)"
kubectl --kubeconfig "$R/secrets/usuarios/luis.lector-prod.kubeconfig" get secret backend-secrets 2>&1 | sed 's/^/  /'
echo "== Acción real permitida (operadora consulta Pods)"
kubectl --kubeconfig "$R/secrets/usuarios/ana.operadora-prod.kubeconfig" get pods -l app.kubernetes.io/name=backend --no-headers 2>&1 | sed 's/^/  /'
echo "== ServiceAccounts de la app sin token montado"
$K get pods -l app.kubernetes.io/name=backend -o jsonpath='{range .items[*]}{.metadata.name} automount={.spec.automountServiceAccountToken}{"\n"}{end}' | sed 's/^/  /'
$K exec deploy/backend -- sh -c 'ls /var/run/secrets/kubernetes.io/serviceaccount 2>&1 || true' | sed 's/^/  /'
echo "  can-i (sa backend) list secrets: $(kubectl --context k3d-ra-prod auth can-i list secrets -n redalimenta --as=system:serviceaccount:redalimenta:backend)"
echo "== PostgreSQL: usuario de ejecución sin DDL ni privilegios administrativos"
q() { $K exec postgres-0 -- psql -h 127.0.0.1 -U postgres -d redalimenta -tAc "$1"; }
$K exec postgres-0 -- psql -U postgres -d redalimenta -tAc "select rolname, rolsuper, rolcreaterole, rolcreatedb from pg_roles where rolname like 'redalimenta%' order by 1" | sed 's/^/  /'
for s in "CREATE TABLE intrusa(x int)" "DROP TABLE lotes" "DELETE FROM outbox" "ALTER TABLE lotes ADD COLUMN x int" "SELECT count(*) FROM lotes"; do
  printf "  app: %-40s -> %s\n" "$s" "$($K exec postgres-0 -- sh -c "psql -U postgres -d redalimenta -v ON_ERROR_STOP=1 -tAc \"SET ROLE redalimenta_app; $s\" 2>&1 | grep -m1 -E 'ERROR|^[0-9]+$'")"; done
for s in "INSERT INTO donantes(nombre,tipo) VALUES ('x','particular')" "SELECT count(*) FROM hogares"; do
  printf "  backup: %-37s -> %s\n" "$s" "$($K exec postgres-0 -- sh -c "psql -U postgres -d redalimenta -v ON_ERROR_STOP=1 -tAc \"SET ROLE redalimenta_backup; $s\" 2>&1 | grep -m1 -E 'ERROR|^[0-9]+$'")"; done
printf "  exporter: %-35s -> %s\n" "SELECT * FROM usuarios" "$($K exec postgres-0 -- sh -c "psql -U postgres -d redalimenta -tAc 'SET ROLE redalimenta_exporter; SELECT count(*) FROM usuarios' 2>&1 | tail -1")"
echo "== MongoDB: usuario de la app limitado a readWrite en redalimenta"
source "$R/secrets/prod.env"
M="mongosh --quiet --norc --tls --tlsCAFile /tls/ca.crt --host localhost -u redalimenta_app -p $MONGO_APP --authenticationDatabase redalimenta"
for js in "db.getSiblingDB('redalimenta').expediente_lote.countDocuments()" "db.getSiblingDB('admin').createUser({user:'x',pwd:'y',roles:[]})" "db.getSiblingDB('redalimenta').dropDatabase()" "db.getSiblingDB('admin').system.users.find().toArray()"; do
  printf "  app: %-62s -> %s\n" "$js" "$($K exec mongo-0 -- $M --eval "$js" 2>&1 | grep -m1 -E 'Error|^[0-9]+$' | cut -c1-110)"; done
