# Imperium Rule Heuristic Graph Schema and Queries

## Current Graph Schema

### Node Labels
- `Imperium_Rule`: Core rule nodes
- `Target_Entity`: Entities targeted by rules
- `Key_Criterion`: Criteria for rule application
- `Exception`: Exclusions from rule scope
- `Compliance_Area`: Domain of compliance
- `Entity_Type`: Type classification for entities
- `Policy_Group`: Policy categories/groups
- `Policy_Name`: Specific policies
- `Rule_Type`: Type of rule
- `Rule_Priority`: Priority level of rule
- `Field`: Data fields referenced by rules
- `Operator`: Operators used in rules
- `Value`: Values used in rule conditions

### Relationship Types
- `TARGETS`: Connects rules to their target entities
- `HAS_CRITERION`: Connects rules to their criteria
- `HAS_EXCEPTION`: Connects rules to their exceptions
- `BELONGS_TO_COMPLIANCE_AREA`: Connects rules to compliance areas
- `HAS_TYPE`: Connects entities to their types
- `HAS_POLICY_GROUP`: Connects rules to policy groups
- `HAS_POLICY_NAME`: Connects rules to policy names
- `BELONGS_TO_GROUP`: Connects policy names to policy groups
- `HAS_TYPE`: Connects rules to rule types
- `HAS_PRIORITY`: Connects rules to rule priorities

### Node Properties
- `Imperium_Rule`:
  - `rule_id`: Unique identifier for the rule
  - `name`: Name of the rule
  - `description`: Description of the rule
  - `intent`: High-level intent of the rule
  - `main_heuristic`: Main pattern/heuristic of the rule
  - `compliance_area`: Area of compliance the rule addresses

- `Target_Entity`:
  - `name`: Name of the entity
  - `original_name`: Original name before normalization
  - `normalized`: Boolean indicating if entity was normalized
  - `entity_types`: Array of entity type names

- `Entity_Type`:
  - `name`: Name of the entity type (e.g., PRODUCT_CATEGORY, BRAND)

- `Key_Criterion`:
  - `description`: Description of the criterion

- `Exception`:
  - `description`: Description of the exception

- `Compliance_Area`:
  - `name`: Name of the compliance area

- `Policy_Group`:
  - `name`: Name of the policy group

- `Policy_Name`:
  - `name`: Name of the policy

## Detailed Cypher Queries

### Basic Schema Exploration

```cypher
// Get all node labels in the graph
CALL db.labels() YIELD label
RETURN label
ORDER BY label;

// Get all relationship types in the graph
CALL db.relationshipTypes() YIELD relationshipType
RETURN relationshipType
ORDER BY relationshipType;

// Count nodes by label
CALL db.labels() YIELD label
CALL apoc.cypher.run('MATCH (:`' + $label + '`) RETURN count(*) as count', {}) YIELD value
RETURN $label as label, value.count as count
ORDER BY count DESC;

// Count relationships by type
CALL db.relationshipTypes() YIELD relationshipType
CALL apoc.cypher.run('MATCH ()-[:`' + $relationshipType + '`]->() RETURN count(*) as count', {}) YIELD value
RETURN $relationshipType as type, value.count as count
ORDER BY count DESC;
```

### Rule Exploration

```cypher
// Get all rules with their metadata
MATCH (rule:Imperium_Rule)
RETURN 
    rule.rule_id as rule_id,
    rule.name as name,
    rule.description as description,
    rule.intent as intent,
    rule.main_heuristic as main_heuristic,
    rule.compliance_area as compliance_area
LIMIT 10;

// Get rules by compliance area
MATCH (rule:Imperium_Rule)
WHERE rule.compliance_area IS NOT NULL
WITH rule.compliance_area as compliance_area, count(*) as count
RETURN compliance_area, count
ORDER BY count DESC;

// Get rules by policy group
MATCH (rule:Imperium_Rule)-[:HAS_POLICY_GROUP]->(pg:Policy_Group)
RETURN pg.name as policy_group, count(rule) as rule_count
ORDER BY rule_count DESC;

// Get complete rule details with all relationships
MATCH (rule:Imperium_Rule)
OPTIONAL MATCH (rule)-[:TARGETS]->(entity:Target_Entity)
OPTIONAL MATCH (rule)-[:HAS_CRITERION]->(criterion:Key_Criterion)
OPTIONAL MATCH (rule)-[:HAS_EXCEPTION]->(exception:Exception)
OPTIONAL MATCH (rule)-[:BELONGS_TO_COMPLIANCE_AREA]->(area:Compliance_Area)
OPTIONAL MATCH (rule)-[:HAS_POLICY_GROUP]->(pg:Policy_Group)
OPTIONAL MATCH (rule)-[:HAS_POLICY_NAME]->(pn:Policy_Name)
WITH 
    rule,
    collect(DISTINCT entity.name) as entities,
    collect(DISTINCT criterion.description) as criteria,
    collect(DISTINCT exception.description) as exceptions,
    collect(DISTINCT area.name) as areas,
    collect(DISTINCT pg.name) as policy_groups,
    collect(DISTINCT pn.name) as policy_names
RETURN 
    rule.rule_id as rule_id,
    rule.name as name,
    rule.description as description,
    rule.intent as intent,
    rule.main_heuristic as main_heuristic,
    rule.compliance_area as compliance_area,
    entities,
    criteria,
    exceptions,
    areas,
    policy_groups,
    policy_names
LIMIT 5;
```

### Entity Analysis

```cypher
// Get all entities with their types and rule counts
MATCH (entity:Target_Entity)
OPTIONAL MATCH (entity)-[:HAS_TYPE]->(type:Entity_Type)
OPTIONAL MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity)
WITH 
    entity,
    collect(DISTINCT type.name) as types,
    count(DISTINCT rule) as rule_count
RETURN 
    entity.name as entity_name,
    entity.original_name as original_name,
    types,
    rule_count
ORDER BY rule_count DESC;

// Get entity type distribution
MATCH (type:Entity_Type)<-[:HAS_TYPE]-(entity:Target_Entity)
RETURN type.name as type, count(entity) as entity_count
ORDER BY entity_count DESC;

// Find entities targeted by multiple rules
MATCH (entity:Target_Entity)<-[:TARGETS]-(rule:Imperium_Rule)
WITH entity, count(rule) as rule_count
WHERE rule_count > 1
RETURN entity.name as entity_name, rule_count
ORDER BY rule_count DESC;

// Get normalized entities with their original names
MATCH (entity:Target_Entity)
WHERE entity.normalized = true
RETURN entity.name as canonical_name, entity.original_name as original_name;
```

### Entity Co-occurrence Analysis

```cypher
// Calculate entity co-occurrence across rules
MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)
WITH rule, collect(entity.name) as entities
UNWIND entities as entity1
UNWIND entities as entity2
WITH entity1, entity2, count(rule) as weight
WHERE entity1 < entity2
RETURN entity1, entity2, weight
ORDER BY weight DESC;

// Create entity co-occurrence network (for visualization)
MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)
WITH rule, collect(entity.name) as entities
WHERE size(entities) > 1
UNWIND entities as entity1
UNWIND entities as entity2
WITH entity1, entity2, count(rule) as weight
WHERE entity1 < entity2
RETURN 
    entity1 as source, 
    entity2 as target, 
    weight,
    "co-occurs" as relationship
ORDER BY weight DESC;
```

### Entity Type Analysis

```cypher
// Get entities by type
MATCH (entity:Target_Entity)-[:HAS_TYPE]->(type:Entity_Type)
WHERE type.name = 'PRODUCT_CATEGORY'  // Can be any type
RETURN entity.name as entity_name
ORDER BY entity_name;

// Get entities with multiple types
MATCH (entity:Target_Entity)-[:HAS_TYPE]->(type:Entity_Type)
WITH entity, collect(type.name) as types
WHERE size(types) > 1
RETURN entity.name as entity_name, types
ORDER BY size(types) DESC;

// Find rules that target entities of specific types
MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)-[:HAS_TYPE]->(type:Entity_Type)
WHERE type.name = 'BRAND'  // Can be any type
RETURN rule.rule_id as rule_id, rule.name as rule_name, entity.name as entity_name
ORDER BY rule_id;
```

### Compliance Area Analysis

```cypher
// Get rules by compliance area with their entities
MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)
WHERE rule.compliance_area IS NOT NULL
RETURN 
    rule.compliance_area as compliance_area,
    collect(DISTINCT rule.rule_id) as rule_ids,
    collect(DISTINCT entity.name) as entities,
    count(DISTINCT rule) as rule_count
ORDER BY rule_count DESC;

// Find common entities across different compliance areas
MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)
WHERE rule.compliance_area IS NOT NULL
WITH entity, collect(DISTINCT rule.compliance_area) as compliance_areas
WHERE size(compliance_areas) > 1
RETURN 
    entity.name as entity_name,
    compliance_areas,
    size(compliance_areas) as area_count
ORDER BY area_count DESC;
```

### Key Criteria Analysis

```cypher
// Get most common criteria across rules
MATCH (criterion:Key_Criterion)<-[:HAS_CRITERION]-(rule:Imperium_Rule)
WITH criterion.description as criterion_description, count(rule) as rule_count
RETURN criterion_description, rule_count
ORDER BY rule_count DESC
LIMIT 10;

// Find rules with similar criteria
MATCH (rule1:Imperium_Rule)-[:HAS_CRITERION]->(criterion:Key_Criterion)<-[:HAS_CRITERION]-(rule2:Imperium_Rule)
WHERE rule1.rule_id < rule2.rule_id
WITH 
    rule1.rule_id as rule1_id,
    rule1.name as rule1_name,
    rule2.rule_id as rule2_id,
    rule2.name as rule2_name,
    collect(DISTINCT criterion.description) as shared_criteria,
    count(DISTINCT criterion) as criteria_count
WHERE criteria_count > 1
RETURN rule1_id, rule1_name, rule2_id, rule2_name, shared_criteria, criteria_count
ORDER BY criteria_count DESC;
```

### Advanced Analysis Queries

```cypher
// Find clusters of rules that target similar entities
MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)
WITH entity, collect(DISTINCT rule.rule_id) as rules
WHERE size(rules) > 1
WITH collect({entity: entity.name, rules: rules}) as entity_clusters
UNWIND entity_clusters as cluster
RETURN cluster.entity as entity_name, cluster.rules as rules;

// Find rules that might be redundant (similar entities and criteria)
MATCH (rule1:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)<-[:TARGETS]-(rule2:Imperium_Rule)
WHERE rule1.rule_id < rule2.rule_id
  AND rule1.policy_group = rule2.policy_group
MATCH (rule1)-[:HAS_CRITERION]->(criterion:Key_Criterion)<-[:HAS_CRITERION]-(rule2)
WITH 
    rule1.rule_id as rule1_id,
    rule1.name as rule1_name,
    rule2.rule_id as rule2_id,
    rule2.name as rule2_name,
    collect(DISTINCT entity.name) as shared_entities,
    count(DISTINCT criterion) as common_criteria_count
WHERE common_criteria_count > 0
RETURN rule1_id, rule1_name, rule2_id, rule2_name, shared_entities, common_criteria_count
ORDER BY common_criteria_count DESC;

// Get entity clusters by type and usage patterns
MATCH (entity:Target_Entity)-[:HAS_TYPE]->(type:Entity_Type)
OPTIONAL MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity)
WITH 
    type.name as entity_type,
    entity.name as entity_name,
    count(DISTINCT rule) as rule_count,
    collect(DISTINCT rule.compliance_area) as compliance_areas
WHERE rule_count > 0
RETURN 
    entity_type,
    collect({name: entity_name, rule_count: rule_count, areas: compliance_areas}) as entities,
    count(DISTINCT entity_name) as entity_count
ORDER BY entity_count DESC;
```

### Entity Normalization Queries

```cypher
// Find similar entities using string matching
MATCH (entity1:Target_Entity), (entity2:Target_Entity)
WHERE entity1.name < entity2.name
  AND apoc.text.jaroWinklerDistance(toLower(entity1.name), toLower(entity2.name)) > 0.8
RETURN entity1.name as entity1_name, entity2.name as entity2_name, 
       apoc.text.jaroWinklerDistance(toLower(entity1.name), toLower(entity2.name)) as similarity
ORDER BY similarity DESC;

// Merge two similar entities (manual normalization)
MATCH (entity1:Target_Entity {name: "Health & Beauty"}), (entity2:Target_Entity {name: "Health & Beauty category"})
WITH entity1, entity2
// Get all relationships from entity2
OPTIONAL MATCH (entity2)<-[r:TARGETS]-(rule:Imperium_Rule)
// Create same relationships to entity1
FOREACH (x IN CASE WHEN r IS NOT NULL THEN [1] ELSE [] END |
  MERGE (rule)-[:TARGETS]->(entity1)
)
// Get all type relationships from entity2
OPTIONAL MATCH (entity2)-[t:HAS_TYPE]->(type:Entity_Type)
// Create same type relationships for entity1
FOREACH (x IN CASE WHEN t IS NOT NULL THEN [1] ELSE [] END |
  MERGE (entity1)-[:HAS_TYPE]->(type)
)
// Set properties on entity1 to indicate normalization
SET entity1.normalized = true, 
    entity1.original_name = CASE WHEN entity1.original_name IS NULL THEN entity1.name ELSE entity1.original_name END
// Delete the redundant entity
DETACH DELETE entity2
RETURN entity1;
```

### Graph Cleanup and Maintenance

```cypher
// Reset normalization status (if needed)
MATCH (entity:Target_Entity)
WHERE entity.normalized = true
REMOVE entity.normalized, entity.original_name
RETURN count(entity);

// Remove duplicate relationships
MATCH (a)-[r:TARGETS]->(b)
WITH a, b, collect(r) as rels
WHERE size(rels) > 1
UNWIND tail(rels) as rel
DELETE rel
RETURN count(rel);

// Create missing indexes for performance
CREATE INDEX imperium_rule_id_idx IF NOT EXISTS FOR (r:Imperium_Rule) ON (r.rule_id);
CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Target_Entity) ON (e.name);
CREATE INDEX entity_type_idx IF NOT EXISTS FOR (t:Entity_Type) ON (t.name);
CREATE INDEX compliance_area_idx IF NOT EXISTS FOR (c:Compliance_Area) ON (c.name);
CREATE INDEX policy_group_idx IF NOT EXISTS FOR (p:Policy_Group) ON (p.name);
CREATE INDEX policy_name_idx IF NOT EXISTS FOR (p:Policy_Name) ON (p.name);
```

## Visualization Queries

### Entity Co-occurrence Network

```cypher
// Generate entity co-occurrence network data
MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)
WITH rule, collect(entity.name) as entities
UNWIND entities as entity1
UNWIND entities as entity2
WITH entity1, entity2, count(rule) as weight
WHERE entity1 < entity2
RETURN 
    entity1 as source, 
    entity2 as target, 
    weight as value,
    weight as label
ORDER BY weight DESC;
```

### Rule-Entity Bipartite Graph

```cypher
// Generate bipartite graph of rules and entities
MATCH (rule:Imperium_Rule)-[:TARGETS]->(entity:Target_Entity)
RETURN 
    rule.rule_id as source,
    entity.name as target,
    "TARGETS" as label,
    rule.compliance_area as source_type,
    collect(DISTINCT entity.entity_types) as target_type
```

### Entity Type Hierarchy

```cypher
// Generate entity type hierarchy
MATCH (entity:Target_Entity)-[:HAS_TYPE]->(type:Entity_Type)
WITH type.name as type_name, collect(entity.name) as entities
RETURN 
    type_name as id,
    type_name as label,
    size(entities) as size,
    "type" as group,
    entities
```

## Export Schema for Use in Other Systems

```cypher
// Export schema to JSON format
CALL apoc.meta.schema() YIELD value
RETURN value;

// Export simplified schema
CALL db.schema.visualization() YIELD nodes, relationships
RETURN 
    [node in nodes | {label: labels(node)[0], properties: keys(node)}] as nodeSchema,
    [rel in relationships | {type: type(rel), source: labels(startNode(rel))[0], target: labels(endNode(rel))[0]}] as relSchema;
```