#!/usr/bin/env python3
import json
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict

# Load the nudity taxonomy JSON data
nudity_taxonomy = {
  "nodes": [
    {
      "id": "Nudity",
      "type": "Category",
      "label": "Root Nudity Category",
      "description": "Root classification covering all visual depictions of partial or full human nakedness, with relevance to compliance, age-restrictions, product guidelines, and trust & safety policies."
    },
    {
      "id": "Explicit_Nudity",
      "type": "Subcategory",
      "label": "Explicit Nudity",
      "description": "Depictions where genitals, breasts, or sexual acts are clearly visible and intended to sexually arouse or offend. Common in adult entertainment products, images, or accessories."
    },
    {
      "id": "Suggestive_Nudity",
      "type": "Subcategory",
      "label": "Suggestive Nudity",
      "description": "Content where nudity is implied but not directly shown, using poses, partial clothing, or strategic coverage that suggests nakedness."
    },
    {
      "id": "Non_Sexual_Nudity",
      "type": "Subcategory",
      "label": "Non-Sexual Nudity",
      "description": "Nudity represented in non-sexual contexts such as art, medicine, or educational content. Often requires nuanced classification to distinguish from inappropriate content."
    },
    {
      "id": "Artistic_Nudity",
      "type": "Subcategory",
      "label": "Artistic Nudity",
      "description": "Classical or modern art forms displaying nudity—paintings, sculptures, and installations—often protected under freedom of expression but needs review in retail/online settings."
    },
    {
      "id": "Child_Nudity",
      "type": "Subcategory",
      "label": "Child Nudity",
      "description": "Any depiction of underage individuals in states of undress, requiring strict monitoring and often prohibited regardless of context."
    },
    {
      "id": "Digitally_Altered_Nudity",
      "type": "Subcategory",
      "label": "AI/Digitally Altered Nudity",
      "description": "Nudity created or modified using digital tools, AI generation, or manipulation techniques."
    },
    {
      "id": "Fetish_Content",
      "type": "Subcategory",
      "label": "Fetish or Kink-Based Nudity",
      "description": "Nudity associated with specific sexual preferences, fetishes, or kink communities, often involving specialized clothing, accessories, or scenarios."
    },
    {
      "id": "Contextual_Nudity",
      "type": "Subcategory",
      "label": "Contextual Nudity (e.g., bath scenes, medical)",
      "description": "Nudity shown within specific contexts that provide legitimate reasons for the display, such as bathing scenes or medical situations."
    },
    {
      "id": "Genital_Exposure",
      "type": "Subcategory",
      "label": "Genital Exposure",
      "description": "Direct visibility of male or female genitalia in any context."
    },
    {
      "id": "Female_Breast_Exposure",
      "type": "Subcategory",
      "label": "Female Breast Exposure (nipples visible)",
      "description": "Content showing female breasts with visible nipples, which may be regulated differently across jurisdictions."
    },
    {
      "id": "Buttocks_Exposure",
      "type": "Subcategory",
      "label": "Full or Partial Buttocks Exposure",
      "description": "Display of buttocks, either partially or fully exposed."
    },
    {
      "id": "Sexual_Acts",
      "type": "Subcategory",
      "label": "Visible Sexual Acts (real or simulated)",
      "description": "Content depicting sexual activities, whether actually performed or simulated."
    },
    {
      "id": "Translucent_Clothing",
      "type": "Subcategory",
      "label": "Nudity through See-Through Apparel",
      "description": "Clothing that is transparent, translucent, or sheer enough to reveal body parts underneath."
    },
    {
      "id": "Erotic_Posing",
      "type": "Subcategory",
      "label": "Erotic or Provocative Posing without Direct Exposure",
      "description": "Poses intended to be sexually suggestive without explicit nudity."
    },
    {
      "id": "Child_Illustrations",
      "type": "Subcategory",
      "label": "Cartoon/AI Child Nudity",
      "description": "Animated, illustrated, or AI-generated depictions of children in states of undress."
    },
    {
      "id": "Deepfake_Nudity",
      "type": "Subcategory",
      "label": "Deepfake Nudity (Face Swaps)",
      "description": "Technology-enabled creation of fake nude imagery by swapping faces onto nude bodies."
    },
    {
      "id": "Virtual_Avatars",
      "type": "Subcategory",
      "label": "Virtual Nudity (Avatars in Games/VR/Metaverse)",
      "description": "Digital representations of nudity in virtual environments, games, or platforms."
    },
    {
      "id": "Nudity_in_Education",
      "type": "Subcategory",
      "label": "Nudity in Medical/Scientific/Educational Context",
      "description": "Nudity presented for educational, scientific, or medical purposes."
    },
    {
      "id": "Cultural_Nudity",
      "type": "Subcategory",
      "label": "Nudity Depicting Ritual/Cultural Traditions",
      "description": "Traditional or cultural practices involving nudity or minimal clothing that reflects specific cultural contexts."
    },
    {
      "id": "Adult_Animated_Nudity",
      "type": "Subcategory",
      "label": "Adult Animated/Cartoon Nudity",
      "description": "Animated or cartoon depictions of adult nudity, including anime, hentai, and adult-oriented cartoons."
    },
    {
      "id": "Accidental_Nudity",
      "type": "Subcategory",
      "label": "Accidental/Unintentional Exposure",
      "description": "Inadvertent exposure of private body parts, often in candid photography, sports events, or wardrobe malfunctions."
    },
    {
      "id": "Entertainment_Nudity",
      "type": "Subcategory",
      "label": "Film/TV Entertainment Nudity",
      "description": "Nudity portrayed in mainstream film, television, or streaming content for artistic or narrative purposes."
    },
    {
      "id": "Historical_Nudity",
      "type": "Subcategory",
      "label": "Historical/Documentary Nudity",
      "description": "Nudity presented in historical contexts or documentary materials, often for educational or archival purposes."
    },
    {
      "id": "Product Safety",
      "type": "ComplianceArea",
      "label": "Product Safety",
      "description": "Regulations ensuring that products meet safety standards and don't pose physical hazards to consumers."
    },
    {
      "id": "Age Restrictions & Sales",
      "type": "ComplianceArea",
      "label": "Age Restrictions & Sales",
      "description": "Laws and policies governing the sale, distribution, and access to age-restricted content and products."
    },
    {
      "id": "Advertising & Marketing",
      "type": "ComplianceArea",
      "label": "Advertising & Marketing",
      "description": "Standards and regulations controlling how nudity can be used in advertisements and marketing materials."
    },
    {
      "id": "Labeling",
      "type": "ComplianceArea",
      "label": "Labeling",
      "description": "Requirements for appropriate content warnings, age advisories, and descriptive labels."
    },
    {
      "id": "Digital Ethics",
      "type": "ComplianceArea",
      "label": "Digital Ethics",
      "description": "Ethical considerations and guidelines for digital content creation, manipulation, and distribution."
    },
    {
      "id": "Platform Content Moderation",
      "type": "ComplianceArea",
      "label": "Platform Content Moderation",
      "description": "Policies and practices used by online platforms to review, filter, and manage nude content."
    },
    {
      "id": "Child Protection",
      "type": "ComplianceArea",
      "label": "Child Protection",
      "description": "Laws and regulations specifically designed to protect minors from exploitation and inappropriate content."
    },
    {
      "id": "Broadcasting Standards",
      "type": "ComplianceArea",
      "label": "Broadcasting Standards",
      "description": "Rules governing nudity in television, radio, and other broadcast media, often with time-of-day restrictions."
    },
    {
      "id": "COPPA",
      "type": "Law/Regulation",
      "label": "Children's Online Privacy Protection Act",
      "description": "U.S. federal law restricting the collection of personal information from children under 13."
    },
    {
      "id": "PROTECT_Act",
      "type": "Law/Regulation",
      "label": "Prosecutorial Remedies and Other Tools to End the Exploitation of Children Today Act",
      "description": "U.S. law prohibiting virtual child pornography and strengthening child exploitation laws."
    },
    {
      "id": "Section230",
      "type": "Law/Regulation",
      "label": "Communications Decency Act - Section 230",
      "description": "U.S. law providing immunity from liability for providers of an interactive computer service who publish information provided by others."
    },
    {
      "id": "FOSTA_SESTA",
      "type": "Law/Regulation",
      "label": "Allow States and Victims to Fight Online Sex Trafficking Act (FOSTA) and Stop Enabling Sex Traffickers Act (SESTA)",
      "description": "U.S. legislation making it easier to target websites that facilitate sex trafficking."
    },
    {
      "id": "State_Obscenity_Laws",
      "type": "Law/Regulation",
      "label": "State-Level Obscenity and Morality Laws",
      "description": "Varying state laws regulating obscene content and nudity based on local community standards."
    },
    {
      "id": "DMCA",
      "type": "Law/Regulation",
      "label": "Digital Millennium Copyright Act",
      "description": "U.S. copyright law addressing digital rights management and copyright infringement liability."
    },
    {
      "id": "FCC_Regulations",
      "type": "Law/Regulation",
      "label": "Federal Communications Commission Regulations",
      "description": "U.S. broadcasting regulations that restrict indecent and obscene content on public airwaves."
    },
    {
      "id": "ASA_CAP_Code",
      "type": "Law/Regulation",
      "label": "Advertising Standards Authority Code of Non-broadcast Advertising and Direct & Promotional Marketing",
      "description": "UK advertising standards that govern content in non-broadcast media."
    }
  ],
  "edges": [
    {
      "source": "Nudity",
      "target": "Explicit_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Suggestive_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Non_Sexual_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Artistic_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Child_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Digitally_Altered_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Fetish_Content",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Contextual_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Adult_Animated_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Accidental_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Entertainment_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Nudity",
      "target": "Historical_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "Genital_Exposure",
      "relationship": "<parent_of>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "Female_Breast_Exposure",
      "relationship": "<parent_of>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "Buttocks_Exposure",
      "relationship": "<parent_of>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "Sexual_Acts",
      "relationship": "<parent_of>"
    },
    {
      "source": "Suggestive_Nudity",
      "target": "Translucent_Clothing",
      "relationship": "<parent_of>"
    },
    {
      "source": "Suggestive_Nudity",
      "target": "Erotic_Posing",
      "relationship": "<parent_of>"
    },
    {
      "source": "Child_Nudity",
      "target": "Child_Illustrations",
      "relationship": "<parent_of>"
    },
    {
      "source": "Digitally_Altered_Nudity",
      "target": "Deepfake_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Digitally_Altered_Nudity",
      "target": "Virtual_Avatars",
      "relationship": "<parent_of>"
    },
    {
      "source": "Non_Sexual_Nudity",
      "target": "Nudity_in_Education",
      "relationship": "<parent_of>"
    },
    {
      "source": "Non_Sexual_Nudity",
      "target": "Cultural_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Non_Sexual_Nudity",
      "target": "Historical_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Contextual_Nudity",
      "target": "Accidental_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Artistic_Nudity",
      "target": "Entertainment_Nudity",
      "relationship": "<parent_of>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "Age Restrictions & Sales",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "Advertising & Marketing",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "Digital Ethics",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "Platform Content Moderation",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "Broadcasting Standards",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Child_Nudity",
      "target": "Child Protection",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Child_Nudity",
      "target": "Digital Ethics",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Child_Nudity",
      "target": "Age Restrictions & Sales",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Child_Nudity",
      "target": "Platform Content Moderation",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Digitally_Altered_Nudity",
      "target": "Platform Content Moderation",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Digitally_Altered_Nudity",
      "target": "Labeling",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Digitally_Altered_Nudity",
      "target": "Digital Ethics",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Artistic_Nudity",
      "target": "Product Safety",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Artistic_Nudity",
      "target": "Labeling",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Artistic_Nudity",
      "target": "Platform Content Moderation",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Suggestive_Nudity",
      "target": "Advertising & Marketing",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Suggestive_Nudity",
      "target": "Digital Ethics",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Suggestive_Nudity",
      "target": "Platform Content Moderation",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Fetish_Content",
      "target": "Age Restrictions & Sales",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Fetish_Content",
      "target": "Platform Content Moderation",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Fetish_Content",
      "target": "Labeling",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Contextual_Nudity",
      "target": "Digital Ethics",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Contextual_Nudity",
      "target": "Platform Content Moderation",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Entertainment_Nudity",
      "target": "Broadcasting Standards",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Entertainment_Nudity",
      "target": "Labeling",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Entertainment_Nudity",
      "target": "Age Restrictions & Sales",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Adult_Animated_Nudity",
      "target": "Platform Content Moderation",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Adult_Animated_Nudity",
      "target": "Age Restrictions & Sales",
      "relationship": "<regulated_by>"
    },
    {
      "source": "Child_Nudity",
      "target": "COPPA",
      "relationship": "<regulated_under>"
    },
    {
      "source": "Child_Nudity",
      "target": "PROTECT_Act",
      "relationship": "<regulated_under>"
    },
    {
      "source": "Child_Illustrations",
      "target": "PROTECT_Act",
      "relationship": "<regulated_under>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "Section230",
      "relationship": "<regulated_under>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "FOSTA_SESTA",
      "relationship": "<regulated_under>"
    },
    {
      "source": "Explicit_Nudity",
      "target": "FCC_Regulations",
      "relationship": "<regulated_under>"
    },
    {
      "source": "Digitally_Altered_Nudity",
      "target": "DMCA",
      "relationship": "<regulated_under>"
    },
    {
      "source": "Nudity",
      "target": "State_Obscenity_Laws",
      "relationship": "<regulated_under>"
    },
    {
      "source": "Entertainment_Nudity",
      "target": "FCC_Regulations",
      "relationship": "<regulated_under>"
    },
    {
      "source": "Suggestive_Nudity",
      "target": "ASA_CAP_Code",
      "relationship": "<regulated_under>"
    },
    {
      "source": "Advertising & Marketing",
      "target": "ASA_CAP_Code",
      "relationship": "<implements>"
    }
  ]
}

# Create a directed graph
G = nx.DiGraph()

# Add nodes with attributes
for node in nudity_taxonomy["nodes"]:
    G.add_node(node["id"], type=node["type"], label=node["label"], 
               description=node.get("description", ""))

# Add edges with attributes
for edge in nudity_taxonomy["edges"]:
    G.add_edge(edge["source"], edge["target"], relationship=edge["relationship"])

# Analyze the taxonomy structure

def analyze_taxonomy():
    # 1. Node type statistics
    node_types = defaultdict(int)
    for node in nudity_taxonomy["nodes"]:
        node_types[node["type"]] += 1

    print("Node type distribution:")
    for node_type, count in node_types.items():
        print(f"  {node_type}: {count}")

    # 2. Edge relationship statistics
    relationship_types = defaultdict(int)
    for edge in nudity_taxonomy["edges"]:
        relationship_types[edge["relationship"]] += 1

    print("\nRelationship type distribution:")
    for rel_type, count in relationship_types.items():
        print(f"  {rel_type}: {count}")

    # 3. Hierarchy analysis
    hierarchy_depth = {}

    def get_depth(node, depth=0):
        children = [target for source, target, data in G.out_edges(node, data=True) 
                    if data.get("relationship") == "<parent_of>"]
        if not children:
            return depth
        return max(get_depth(child, depth + 1) for child in children)

    root_nodes = [node for node in G.nodes() if G.nodes[node]["type"] == "Category"]
    for root in root_nodes:
        hierarchy_depth[root] = get_depth(root)

    print("\nHierarchy depth analysis:")
    for root, depth in hierarchy_depth.items():
        print(f"  {root}: {depth} levels deep")

    # 4. Compliance connection analysis
    compliance_areas = [node for node in G.nodes() if G.nodes[node]["type"] == "ComplianceArea"]
    regulations = [node for node in G.nodes() if G.nodes[node]["type"] == "Law/Regulation"]

    print("\nCompliance area connections:")
    for area in compliance_areas:
        connected_categories = [source for source, target, data in G.in_edges(area, data=True) 
                            if data.get("relationship") == "<regulated_by>"]
        print(f"  {area}: {len(connected_categories)} category connections")
        for category in connected_categories:
            print(f"    - {category}")

    print("\nRegulatory framework connections:")
    for reg in regulations:
        connected_categories = [source for source, target, data in G.in_edges(reg, data=True) 
                            if data.get("relationship") == "<regulated_under>"]
        print(f"  {reg}: {len(connected_categories)} category connections")
        for category in connected_categories:
            print(f"    - {category}")

    # 5. Node connection analysis (degree centrality)
    print("\nNode connection analysis (top 10 by degree):")
    degree_dict = dict(G.degree())
    for node, degree in sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)[:10]:
        node_type = G.nodes[node]["type"]
        print(f"  {node} ({node_type}): {degree} connections")

    # 6. Identify isolated nodes or subgraphs
    print("\nIsolated nodes or components:")
    if nx.number_connected_components(G.to_undirected()) > 1:
        for component in nx.connected_components(G.to_undirected()):
            if len(component) < len(G):
                print(f"  Isolated component found with {len(component)} nodes:")
                for node in component:
                    print(f"    - {node} ({G.nodes[node]['type']})")
    else:
        print("  No isolated components found.")

    # 7. Check for subcategories without regulatory connections
    subcategories = [node for node in G.nodes() if G.nodes[node]["type"] == "Subcategory"]
    print("\nSubcategories without regulatory connections:")
    for subcat in subcategories:
        has_regulation = False
        for _, target, data in G.out_edges(subcat, data=True):
            if data.get("relationship") in ["<regulated_by>", "<regulated_under>"]:
                has_regulation = True
                break
        if not has_regulation:
            print(f"  {subcat} has no direct regulatory connections")

def visualize_taxonomy():
    # Visualize the graph
    plt.figure(figsize=(20, 20))
    pos = nx.spring_layout(G, seed=42, k=0.3)  # k controls spacing

    # Draw nodes with different colors based on type
    node_colors = {"Category": "#ff9999", "Subcategory": "#99ccff", 
                "ComplianceArea": "#99ff99", "Law/Regulation": "#ffcc99"}
    for node_type, color in node_colors.items():
        nodes = [node for node in G.nodes() if G.nodes[node]["type"] == node_type]
        nx.draw_networkx_nodes(G, pos, nodelist=nodes, node_color=color, node_size=300)

    # Draw edges with different colors based on relationship
    edge_colors = {"<parent_of>": "blue", "<regulated_by>": "green", 
                "<regulated_under>": "red", "<implements>": "purple"}
    for rel_type, color in edge_colors.items():
        edges = [(s, t) for s, t, data in G.edges(data=True) if data.get("relationship") == rel_type]
        nx.draw_networkx_edges(G, pos, edgelist=edges, edge_color=color, width=1.5, alpha=0.7)

    # Add node labels
    nx.draw_networkx_labels(G, pos, font_size=8)

    # Add a legend
    legend_elements = []
    for node_type, color in node_colors.items():
        import matplotlib.patches as mpatches
        legend_elements.append(mpatches.Patch(facecolor=color, edgecolor='k', label=node_type))
    for rel_type, color in edge_colors.items():
        import matplotlib.lines as mlines
        legend_elements.append(mlines.Line2D([], [], color=color, label=rel_type))

    plt.legend(handles=legend_elements, loc='best')
    plt.title("Nudity Taxonomy Graph Visualization")
    plt.axis('off')
    plt.tight_layout()
    plt.savefig("nudity_taxonomy_graph.png", dpi=300)
    print("\nGraph visualization saved to 'nudity_taxonomy_graph.png'")

def export_to_json():
    # Export the taxonomy to JSON file
    with open('enhanced_nudity_taxonomy.json', 'w') as f:
        json.dump(nudity_taxonomy, f, indent=2)
    print("Enhanced taxonomy exported to 'enhanced_nudity_taxonomy.json'")

if __name__ == "__main__":
    print("Enhanced Nudity Taxonomy Analysis")
    print("=" * 40)
    analyze_taxonomy()
    visualize_taxonomy()
    export_to_json()