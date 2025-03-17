// 1. Basic node counts
MATCH (n)
RETURN labels(n) AS nodeType, count(*) AS count
ORDER BY count DESC;

// 2. View the entire taxonomy structure (limited to 25 relationships)
MATCH p=()-[r]->() 
RETURN p
LIMIT 25;

// 3. See the hierarchy from the root category to subcategories
MATCH path = (:Category {id: 'Weapons'})-[:PARENT_OF]->(subcategory:Subcategory)
RETURN path;

// 4. Get all compliance areas with their connected laws/regulations
MATCH (ca:ComplianceArea)-[r:GOVERNED_BY]->(law:Law_Regulation)
RETURN ca.id AS complianceArea, collect(law.id) AS governingLaws
ORDER BY complianceArea;

// 5. Find all subcategories regulated by a specific compliance area
MATCH (s:Subcategory)-[r:REGULATED_BY]->(ca:ComplianceArea {id: 'Product Safety'})
RETURN s.id AS subcategory, s.label AS description, r.notes AS regulations;

// 6. Find weapon subcategories related to specific keywords (e.g., "explosives")
MATCH (s:Subcategory)
WHERE s.id CONTAINS 'Explosive' OR s.label CONTAINS 'explosive'
RETURN s.id, s.label;

// 7. Find all laws that regulate multiple compliance areas
MATCH (ca:ComplianceArea)-[:GOVERNED_BY]->(law:Law_Regulation)
WITH law, collect(ca.id) AS areas, count(ca) AS areaCount
WHERE areaCount > 1
RETURN law.id AS law, law.label AS fullName, areas, areaCount
ORDER BY areaCount DESC;

// 8. Find complete regulatory paths for a specific subcategory
MATCH path = (s:Subcategory {id: 'Firearms'})-[:REGULATED_BY]->(ca:ComplianceArea)
             -[:GOVERNED_BY]->(l:Law_Regulation)
RETURN s.id AS subcategory, ca.id AS complianceArea, l.id AS law;

// 9. Find regulations about specific issues (keyword search on notes)
MATCH (s:Subcategory)-[r:REGULATED_BY]->(ca:ComplianceArea)
WHERE any(note IN r.notes WHERE note CONTAINS 'export')
RETURN s.id AS subcategory, ca.id AS complianceArea, r.notes AS regulations;

// 10. Find compliance areas with the most laws/regulations
MATCH (ca:ComplianceArea)-[:GOVERNED_BY]->(law:Law_Regulation)
WITH ca, count(law) AS lawCount
RETURN ca.id AS complianceArea, lawCount
ORDER BY lawCount DESC;

// 11. Find subcategories with the most compliance areas
MATCH (s:Subcategory)-[:REGULATED_BY]->(ca:ComplianceArea)
WITH s, count(ca) AS complianceCount
RETURN s.id AS subcategory, complianceCount
ORDER BY complianceCount DESC;

// 12. Find all regulations related to age restrictions
MATCH (s:Subcategory)-[r:REGULATED_BY]->(ca:ComplianceArea {id: 'Age Restrictions & Sales'})
RETURN s.id AS subcategory, r.notes AS ageRestrictions
ORDER BY s.id;

// 13. Complex path query - Find subcategories regulated by compliance areas governed by the Gun Control Act
MATCH path = (s:Subcategory)-[:REGULATED_BY]->(ca:ComplianceArea)
             -[:GOVERNED_BY]->(l:Law_Regulation {id: 'Gun Control Act (GCA)'})
RETURN s.id AS subcategory, ca.id AS complianceArea
ORDER BY s.id, ca.id;

// 14. Find regulatory similarities between weapons - common compliance areas
MATCH (s1:Subcategory {id: 'Firearms'})-[:REGULATED_BY]->(ca:ComplianceArea)<-[:REGULATED_BY]-(s2:Subcategory)
WHERE s1 <> s2
RETURN s2.id AS relatedWeapon, collect(ca.id) AS sharedComplianceAreas, count(ca) AS commonAreasCount
ORDER BY commonAreasCount DESC;

// 15. Graph visualization of subcategories linked to a specific law through compliance areas
MATCH path = (s:Subcategory)-[:REGULATED_BY]->(ca:ComplianceArea)
             -[:GOVERNED_BY]->(l:Law_Regulation {id: 'ITAR'})
RETURN path;