#!/bin/bash
# Script to check the status of all running processes

PROJECT_ROOT="/Users/arunmenon/projects/apparels-entity-extractor"

# Function to check process status
check_process() {
  local pid_file=$1
  local name=$2
  
  if [ ! -f "$pid_file" ]; then
    echo "$name: Process not started (no PID file)"
    return
  fi
  
  pid=$(cat "$pid_file")
  if ps -p "$pid" > /dev/null; then
    echo "$name: Running (PID: $pid)"
  else
    echo "$name: Completed or terminated (PID was: $pid)"
  fi
}

echo "=== Augmentation Process Status ==="
check_process "$PROJECT_ROOT/priority_output/fashion/fashion_pid.txt" "Fashion augmentation"
check_process "$PROJECT_ROOT/priority_output/arts_crafts/arts_crafts_pid.txt" "Arts & Crafts augmentation"
check_process "$PROJECT_ROOT/priority_output/garden_patio/garden_patio_pid.txt" "Garden & Patio augmentation"

echo ""
echo "=== Compliance Analysis Status ==="
# Check if directory exists first
if [ -d "$PROJECT_ROOT/priority_output/compliance_analysis" ]; then
  check_process "$PROJECT_ROOT/priority_output/compliance_analysis/fashion_nudity_pid.txt" "Fashion vs Nudity analysis"
  check_process "$PROJECT_ROOT/priority_output/compliance_analysis/arts_crafts_nudity_pid.txt" "Arts & Crafts vs Nudity analysis"
  check_process "$PROJECT_ROOT/priority_output/compliance_analysis/garden_patio_weapons_pid.txt" "Garden & Patio vs Weapons analysis"
else
  echo "Compliance analysis not started yet"
fi

echo ""
echo "=== Output File Status ==="
check_file() {
  local file_path=$1
  local file_name=$2
  
  if [ -f "$file_path" ]; then
    size=$(du -h "$file_path" | cut -f1)
    echo "$file_name: Exists (Size: $size)"
  else
    echo "$file_name: Not created yet"
  fi
}

echo "Augmentation Output:"
check_file "$PROJECT_ROOT/priority_output/fashion/augmented_taxonomy.json" "Fashion taxonomy"
check_file "$PROJECT_ROOT/priority_output/arts_crafts/augmented_taxonomy.json" "Arts & Crafts taxonomy"
check_file "$PROJECT_ROOT/priority_output/garden_patio/augmented_taxonomy.json" "Garden & Patio taxonomy"

if [ -d "$PROJECT_ROOT/product_taxonomy" ]; then
  echo ""
  echo "Compliance Analysis Output:"
  check_file "$PROJECT_ROOT/product_taxonomy/Fashion_Nudity/complete_analysis.json" "Fashion-Nudity analysis"
  check_file "$PROJECT_ROOT/product_taxonomy/Arts & Crafts_Nudity/complete_analysis.json" "Arts & Crafts-Nudity analysis"
  check_file "$PROJECT_ROOT/product_taxonomy/Garden & Patio_Weapons/complete_analysis.json" "Garden & Patio-Weapons analysis"
  
  check_file "$PROJECT_ROOT/product_taxonomy/Fashion_Nudity/graph_structure.json" "Fashion-Nudity graph structure"
  check_file "$PROJECT_ROOT/product_taxonomy/Arts & Crafts_Nudity/graph_structure.json" "Arts & Crafts-Nudity graph structure"
  check_file "$PROJECT_ROOT/product_taxonomy/Garden & Patio_Weapons/graph_structure.json" "Garden & Patio-Weapons graph structure"
fi

echo ""
echo "To view detailed logs:"
echo "- Augmentation logs:"
echo "  tail -f $PROJECT_ROOT/priority_output/fashion/augment_log.txt"
echo "  tail -f $PROJECT_ROOT/priority_output/arts_crafts/augment_log.txt"
echo "  tail -f $PROJECT_ROOT/priority_output/garden_patio/augment_log.txt"

if [ -d "$PROJECT_ROOT/priority_output/compliance_analysis" ]; then
  echo "- Compliance analysis logs:"
  echo "  tail -f $PROJECT_ROOT/priority_output/compliance_analysis/fashion_nudity.log"
  echo "  tail -f $PROJECT_ROOT/priority_output/compliance_analysis/arts_crafts_nudity.log"
  echo "  tail -f $PROJECT_ROOT/priority_output/compliance_analysis/garden_patio_weapons.log"
fi