// Generic Taxonomy Queries for Neo4j
// These queries work with any taxonomy following the standard graph schema

// 1. Basic node counts
MATCH (n)
RETURN labels(n) AS nodeType, count(*) AS count
ORDER BY count DESC;

// 2. Find all categories (root nodes)
MATCH (c:Category)
RETURN c.id AS category, c.label AS label, c.description AS description;

// 3. Display hierarchical structure for a specific category
// Replace 'Weapons' with your category name
MATCH path = (:Category {id: 'Weapons'})-[:PARENT_OF*1..5]->(child)
WITH child, length(path) AS depth
MATCH (parent)-[:PARENT_OF]->(child)
RETURN 
  CASE 
    WHEN depth = 1 THEN child.id
    WHEN depth = 2 THEN "  ├── " + child.id
    WHEN depth = 3 THEN "  │   ├── " + child.id
    WHEN depth = 4 THEN "  │   │   ├── " + child.id
    WHEN depth = 5 THEN "  │   │   │   ├── " + child.id
    ELSE "  │   │   │   │   ├── " + child.id
  END AS hierarchy,
  child.label AS description,
  depth,
  parent.id AS parent
ORDER BY depth, child.id;

// 4. Find all compliance areas
MATCH (ca:ComplianceArea)
RETURN ca.id AS area, ca.label AS label, ca.description AS description
ORDER BY area;

// 5. Find all laws and regulations
MATCH (l:Law_Regulation)
RETURN l.id AS law, l.label AS name, l.description AS description
ORDER BY law;

// 6. Show subcategories regulated by a specific compliance area
// Replace 'Product Safety' with your compliance area
MATCH (s)-[r:REGULATED_BY]->(ca:ComplianceArea {id: 'Product Safety'})
RETURN s.id AS subcategory, s.label AS label, r.notes AS regulations
ORDER BY subcategory;

// 7. Show laws governing a specific compliance area
// Replace 'Trade Compliance' with your compliance area
MATCH (ca:ComplianceArea {id: 'Trade Compliance'})-[r:GOVERNED_BY]->(l:Law_Regulation)
RETURN l.id AS law, l.label AS name, r.scope AS scope
ORDER BY law;

// 8. Find complete regulatory path for a subcategory
// Replace 'Firearms' with your subcategory
MATCH path = (s {id: 'Firearms'})-[:REGULATED_BY]->(ca:ComplianceArea)
            -[:GOVERNED_BY]->(l:Law_Regulation)
RETURN s.id AS subcategory, ca.id AS compliance_area, l.id AS law
ORDER BY ca.id, l.id;

// 9. Find subcategories with no regulatory connections
MATCH (s:Subcategory)
WHERE NOT (s)-[:REGULATED_BY]->() AND NOT (s)-[:REGULATED_UNDER]->()
RETURN s.id AS subcategory, s.label AS description;

// 10. Find regulations with specific keywords in their description
// Replace 'export' with your keyword
MATCH (l:Law_Regulation)
WHERE l.description CONTAINS 'export' OR l.label CONTAINS 'export'
RETURN l.id AS law, l.label AS name, l.description AS description;

// 11. Find relationships between subcategories (common compliance areas)
// Replace 'Firearms' and 'Ammunition' with your subcategories
MATCH (s1:Subcategory {id: 'Firearms'})-[:REGULATED_BY]->(ca:ComplianceArea)<-[:REGULATED_BY]-(s2:Subcategory {id: 'Ammunition'})
RETURN ca.id AS shared_compliance_area, ca.label AS area_name;

// 12. Find all relationships of a specific subcategory
// Replace 'Firearms' with your subcategory
MATCH (s:Subcategory {id: 'Firearms'})-[r]->(n)
RETURN type(r) AS relationship_type, n.id AS connected_node, labels(n) AS node_type;

// 13. Find compliance areas with the most regulations
MATCH (ca:ComplianceArea)-[:GOVERNED_BY]->(l:Law_Regulation)
WITH ca, count(l) AS regulation_count
RETURN ca.id AS compliance_area, ca.label AS name, regulation_count
ORDER BY regulation_count DESC;

// 14. Find subcategories with the most compliance connections
MATCH (s:Subcategory)-[:REGULATED_BY]->(ca:ComplianceArea)
WITH s, count(ca) AS compliance_count
RETURN s.id AS subcategory, s.label AS name, compliance_count
ORDER BY compliance_count DESC
LIMIT 10;

// 15. Find orphaned nodes (no relationships)
MATCH (n)
WHERE NOT (n)--()
RETURN labels(n) AS node_type, n.id AS id, n.label AS label;

// 16. Search for nodes by keyword
// Replace 'knife' with your keyword
MATCH (n)
WHERE n.id CONTAINS 'knife' OR n.label CONTAINS 'knife' OR n.description CONTAINS 'knife'
RETURN labels(n) AS node_type, n.id AS id, n.label AS label;

// 17. Find similar subcategories (based on regulatory profile)
// Replace 'Firearms' with your subcategory
MATCH (s1:Subcategory {id: 'Firearms'})-[:REGULATED_BY]->(ca:ComplianceArea)<-[:REGULATED_BY]-(s2:Subcategory)
WHERE s1 <> s2
WITH s2, count(ca) AS common_areas
MATCH (s1:Subcategory {id: 'Firearms'})-[:REGULATED_BY]->(ca:ComplianceArea)
WITH s2, common_areas, count(ca) AS total_areas
RETURN s2.id AS similar_subcategory, s2.label AS name, 
       common_areas AS shared_compliance_areas,
       total_areas AS total_compliance_areas,
       100.0 * common_areas / total_areas AS similarity_percentage
ORDER BY similarity_percentage DESC;

// 18. Find the most connected node (highest degree centrality)
MATCH (n)
RETURN labels(n) AS node_type, n.id AS id, n.label AS label, size((n)--()) AS connection_count
ORDER BY connection_count DESC
LIMIT 10;

// 19. Visualize a small subgraph around a specific node
// Replace 'Firearms' with your node ID
MATCH path = (n {id: 'Firearms'})-[r*1..2]-(connected)
RETURN path
LIMIT 25;

// LEGACY COMPATIBILITY QUERIES

// L1. Get all Product Categories (legacy schema)
MATCH (cat:Product_Category)
RETURN cat.name AS Category
ORDER BY Category;

// L2. Get all Compliance Areas for a category (legacy schema)
MATCH (cat:Product_Category {name: "Apparel & Footwear"})-[:HAS_COMPLIANCE_AREA]->(area:Compliance_Area)
RETURN area.name AS ComplianceArea
ORDER BY ComplianceArea;

// L3. Get all Regulations for a compliance area (legacy schema)
MATCH (area:Compliance_Area {name: "Product Safety"})-[:HAS_REGULATION]->(reg:Regulation)
RETURN area.name AS Area, reg.name AS Regulation, reg.citation AS Citation
ORDER BY Regulation;