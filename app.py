import os
import re
import json
import io
from pathlib import Path
import streamlit as st
import networkx as nx
import plotly.graph_objects as go

# Optional LLM support. The app still works without an API key.
try:
    from google import genai
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False

# RAG stack: ChromaDB stores vectors; Sentence Transformers creates embeddings.
try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    RAG_AVAILABLE = True
except Exception:
    chromadb = None
    SentenceTransformer = None
    RAG_AVAILABLE = False

st.set_page_config(
    page_title="Presidency Campus Guide",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------------
# CAMPUS DATA
# Important: locations and links below are an approximate first draft
# derived from the two maps supplied by the student. Verify on campus.
# Coordinates are schematic layout coordinates, NOT GPS coordinates.
# -------------------------------------------------------------------
LOCATIONS = {
    "University Entrance": (50, 4, "Entrance"),
    "Fountain": (50, 34, "Landmark"),
    "School of Engineering": (45, 59, "Academic"),
    "Admission Office": (61, 55, "Office"),
    "Office of the Registrar": (66, 53, "Office"),
    "School of Commerce": (64, 68, "Academic"),
    "School of Design": (79, 52, "Academic"),
    "School of Law": (63, 88, "Academic"),
    "School of Media Studies": (74, 85, "Academic"),
    "Workshop": (77, 98, "Facility"),
    "Cafeteria": (23, 57, "Food"),
    "Auditorium": (24, 62, "Facility"),
    "School of Management": (23, 69, "Academic"),
    "Medical Room": (34, 57, "Service"),
    "Transport Office": (32, 54, "Office"),
    "Fee Counter": (41, 55, "Office"),
    "HR Office": (47, 55, "Office"),
    "DSA Office": (38, 64, "Office"),
    "Hostel Mess": (31, 29, "Food"),
    "Parking Area": (32, 18, "Parking"),
    "Sports Field": (60, 29, "Sports"),
    "Cricket Pitch": (68, 39, "Sports"),
    "Subway": (35, 52, "Food"),
    "Hatti Kaapi": (43, 51, "Food"),
    "Cafe Taj Delight": (76, 47, "Food"),
    "Aroma of Malnad": (53, 49, "Food"),
    "Stationery": (73, 52, "Shop"),
    "Seminar Hall 1": (80, 74, "Facility"),
    "Seminar Hall 2": (80, 71, "Facility"),
    "Seminar Hall 3": (80, 65, "Facility"),
    "Seminar Hall 4": (80, 62, "Facility"),
    "U-Block": (64, 93, "Block"),
    "R-Block": (64, 90, "Block"),
    "Q-Block": (64, 86, "Block"),
    "P-Block": (64, 81, "Block"),
    "N-Block": (64, 77, "Block"),
    "K-Block": (64, 73, "Block"),
    "J-Block": (64, 68, "Block"),
    "H-Block": (56, 62, "Block"),
    "L-Block": (80, 80, "Block"),
    "F-Block": (80, 71, "Block"),
    "E-Block": (80, 64, "Block"),
    "D-Block": (85, 55, "Block"),
}

ALIASES = {
    "entrance": "University Entrance", "main gate": "University Entrance",
    "gate": "University Entrance", "engineering": "School of Engineering",
    "school of engineering": "School of Engineering", "admission": "Admission Office",
    "admissions": "Admission Office", "admission office": "Admission Office",
    "registrar": "Office of the Registrar", "registrar office": "Office of the Registrar",
    "canteen": "Cafeteria", "cafe": "Cafeteria", "cafeteria": "Cafeteria",
    "mess": "Hostel Mess", "management": "School of Management",
    "commerce": "School of Commerce", "design": "School of Design",
    "law": "School of Law", "media": "School of Media Studies",
    "sports": "Sports Field", "field": "Sports Field", "parking": "Parking Area",
    "fountain": "Fountain", "subway": "Subway", "hatti kaapi": "Hatti Kaapi",
    "cafe taj": "Cafe Taj Delight", "cafe taj delight": "Cafe Taj Delight",
    "aroma": "Aroma of Malnad", "stationery": "Stationery", "workshop": "Workshop",
    "medical": "Medical Room", "medical room": "Medical Room",
    "fee counter": "Fee Counter", "hr office": "HR Office",
    "transport office": "Transport Office", "dsa": "DSA Office",
    "cricket": "Cricket Pitch", "cricket pitch": "Cricket Pitch",
}
for location in LOCATIONS:
    ALIASES[location.lower()] = location
    ALIASES[location.replace("-", " ").lower()] = location

G = nx.Graph()
for name, (x, y, category) in LOCATIONS.items():
    G.add_node(name, pos=(x, y), category=category)

# Approximate walkable connections; update these after an on-campus walkthrough.
EDGES = [
    ("University Entrance", "Fountain"),
    ("Fountain", "School of Engineering"),
    ("Fountain", "Admission Office"),
    ("Admission Office", "Office of the Registrar"),
    ("Office of the Registrar", "School of Commerce"),
    ("Office of the Registrar", "School of Design"),
    ("School of Commerce", "School of Engineering"),
    ("School of Design", "Cafe Taj Delight"),
    ("School of Design", "Stationery"),
    ("School of Commerce", "Seminar Hall 4"),
    ("Seminar Hall 4", "Seminar Hall 3"),
    ("Seminar Hall 3", "Seminar Hall 2"),
    ("Seminar Hall 2", "Seminar Hall 1"),
    ("Seminar Hall 1", "L-Block"),
    ("L-Block", "P-Block"),
    ("P-Block", "Q-Block"),
    ("Q-Block", "R-Block"),
    ("R-Block", "U-Block"),
    ("P-Block", "School of Law"),
    ("Q-Block", "School of Media Studies"),
    ("School of Law", "School of Media Studies"),
    ("School of Media Studies", "Workshop"),
    ("School of Engineering", "H-Block"),
    ("H-Block", "J-Block"),
    ("J-Block", "K-Block"),
    ("K-Block", "N-Block"),
    ("N-Block", "P-Block"),
    ("School of Engineering", "HR Office"),
    ("HR Office", "Fee Counter"),
    ("Fee Counter", "Hatti Kaapi"),
    ("Hatti Kaapi", "Subway"),
    ("Subway", "Cafeteria"),
    ("Cafeteria", "Auditorium"),
    ("Auditorium", "School of Management"),
    ("Cafeteria", "Fountain"),
    ("School of Management", "Parking Area"),
    ("Parking Area", "Hostel Mess"),
    ("Hostel Mess", "Fountain"),
    ("Fountain", "Sports Field"),
    ("Sports Field", "Cricket Pitch"),
    ("Sports Field", "Aroma of Malnad"),
    ("Aroma of Malnad", "Admission Office"),
    ("Admission Office", "School of Engineering"),
    ("School of Commerce", "D-Block"),
    ("D-Block", "Stationery"),
    ("Cafe Taj Delight", "D-Block"),
    ("School of Engineering", "Medical Room"),
    ("Medical Room", "Transport Office"),
    ("Transport Office", "DSA Office"),
    ("DSA Office", "School of Management"),
    ("School of Engineering", "Fee Counter"),
    ("School of Commerce", "School of Design"),
]
for a, b in EDGES:
    G.add_edge(a, b, weight=1)

def clean_text(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s-]", " ", value.lower())).strip()

def resolve_location(text):
    cleaned = clean_text(text)
    for alias in sorted(ALIASES, key=len, reverse=True):
        if re.search(r"(?<!\w)" + re.escape(clean_text(alias)) + r"(?!\w)", cleaned):
            return ALIASES[alias]
    return None

def parse_question_rules(question, current_start):
    """Parse explicit campus routes locally, without waiting for Gemini."""
    q = question.lower().strip()

    # Explicit format: "from X to Y".
    match = re.search(r"\bfrom\s+(.+?)\s+\bto\s+(.+?)(?:[?.!,]|$)", q)
    if match:
        start = resolve_location(match.group(1))
        destination = resolve_location(match.group(2))
        if start and destination:
            return {"intent": "route", "start": start, "destination": destination}

    # Explicit format: "get/go to Y from X".
    match = re.search(
        r"\b(?:get|go|walk|travel|reach)\s+to\s+(.+?)\s+\bfrom\s+(.+?)(?:[?.!,]|$)", q
    )
    if match:
        destination = resolve_location(match.group(1))
        start = resolve_location(match.group(2))
        if start and destination:
            return {"intent": "route", "start": start, "destination": destination}

    # Also support "directions to Y from X" and "route to Y from X".
    match = re.search(
        r"\b(?:directions?|route)\s+to\s+(.+?)\s+\bfrom\s+(.+?)(?:[?.!,]|$)", q
    )
    if match:
        destination = resolve_location(match.group(1))
        start = resolve_location(match.group(2))
        if start and destination:
            return {"intent": "route", "start": start, "destination": destination}

    # If two known locations appear in a question with route language, use the
    # direction words to identify which is the origin and which is the destination.
    if any(word in q for word in ["how do i", "directions", "route", "get to", "go to", "reach"]):
        if " from " in f" {q} ":
            before, after = re.split(r"\bfrom\b", q, maxsplit=1, flags=re.I)
            start = resolve_location(after)
            destination = resolve_location(before)
            if start and destination and start != destination:
                return {"intent": "route", "start": start, "destination": destination}
        found = []
        for alias in sorted(ALIASES, key=len, reverse=True):
            cleaned_alias = clean_text(alias)
            if re.search(r"(?<!\w)" + re.escape(cleaned_alias) + r"(?!\w)", clean_text(q)):
                canonical = ALIASES[alias]
                if canonical not in found:
                    found.append(canonical)
        if len(found) >= 2:
            # For a plain "from X to Y" question, the first location is the origin.
            return {"intent": "route", "start": found[0], "destination": found[1]}
        destination = resolve_location(q)
        if destination:
            return {"intent": "route", "start": current_start, "destination": destination}

    if any(word in q for word in ["food", "eat", "hungry", "coffee", "snack", "lunch"]):
        food_places = ["Cafeteria", "Subway", "Hatti Kaapi", "Cafe Taj Delight", "Aroma of Malnad", "Hostel Mess"]
        return {"intent": "food", "start": current_start, "destination": None, "suggestions": food_places}

    if any(word in q for word in ["block", "office", "building", "place", "locations"]):
        return {"intent": "help", "start": current_start, "destination": None}
    return {"intent": "unknown", "start": current_start, "destination": None}

def parse_question_gemini(question, current_start, api_key):
    """Use Gemini only to extract structured intent; routes are always computed locally."""
    if not (GEMINI_AVAILABLE and api_key):
        return None
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
You are the intent parser for a university campus navigation application.
Return ONLY valid JSON with keys intent, start, destination, category.
intent must be one of: route, find_place, food, help, unknown.
Use only exact location names from this list:
{list(LOCATIONS.keys())}
Current starting location: {current_start}
Student question: {question}
Rules:
- Never invent a location. Use null if you cannot confidently map it.
- For "where is X", set intent=find_place and destination=X.
- For "from X to Y", set intent=route, start=X, destination=Y.
- For nearest food/coffee, set intent=food.
- Do not generate route directions.
"""
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text)
        if data.get("start") not in LOCATIONS:
            data["start"] = current_start
        if data.get("destination") not in LOCATIONS:
            data["destination"] = None
        return data
    except Exception:
        return None

# ------------------------- RAG / CHROMADB -------------------------
# The starter knowledge base is generated only from the campus directory and
# draft route graph already present in this project. It does not invent hours,
# building descriptions, distances, or verified walking instructions.
RAG_CHUNK_SIZE_DEFAULT = 450
RAG_CHUNK_OVERLAP_DEFAULT = 80
RAG_TOP_K_DEFAULT = 3
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

def build_campus_documents():
    docs = [
        {"id": "overview", "text": "Presidency University campus guide for the Yelahanka campus in Bengaluru. This knowledge base is a starter directory generated from the locations and draft route graph in this application. The map coordinates and connections are approximate and require on-campus verification."},
    ]
    for name, (x, y, category) in LOCATIONS.items():
        docs.append({
            "id": "location_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
            "text": f"{name} is listed in the Presidency University campus directory. Category: {category}. It appears on the application's schematic campus map. The map position is approximate and should be verified on campus.",
        })
    categories = {}
    for name, (_, _, category) in LOCATIONS.items():
        categories.setdefault(category, []).append(name)
    for category, names in categories.items():
        docs.append({
            "id": "category_" + re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_"),
            "text": f"Campus locations categorized as {category}: " + ", ".join(names) + ". This is the application's draft directory; confirm current availability and exact locations with campus signage.",
        })
    # Include only connections explicitly present in the current draft graph.
    for a, b in EDGES:
        docs.append({
            "id": "connection_" + re.sub(r"[^a-z0-9]+", "_", a.lower()) + "_" + re.sub(r"[^a-z0-9]+", "_", b.lower()),
            "text": f"The current draft campus route graph contains a connection between {a} and {b}. This edge is an unverified prototype connection, not a surveyed pedestrian path.",
        })
    return docs

def split_text_into_chunks(text, chunk_size=RAG_CHUNK_SIZE_DEFAULT, overlap=RAG_CHUNK_OVERLAP_DEFAULT):
    """Split text into overlapping word chunks for embedding and retrieval."""
    words = text.split()
    if not words:
        return []
    chunk_size = max(50, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size // 2))
    chunks, start = [], 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks

@st.cache_resource(show_spinner="Loading embedding model and building the ChromaDB campus index...")
def load_rag_index(chunk_size=RAG_CHUNK_SIZE_DEFAULT, chunk_overlap=RAG_CHUNK_OVERLAP_DEFAULT):
    """Create an in-memory ChromaDB collection populated with sentence embeddings."""
    if not RAG_AVAILABLE:
        raise RuntimeError("RAG dependencies are unavailable. Install chromadb and sentence-transformers.")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    client = chromadb.Client()
    collection = client.create_collection(
        name="presidency_campus_" + str(chunk_size) + "_" + str(chunk_overlap),
        metadata={"hnsw:space": "cosine"},
    )
    chunk_ids, chunk_texts, metadatas = [], [], []
    for doc in build_campus_documents():
        for index, chunk in enumerate(split_text_into_chunks(doc["text"], chunk_size, chunk_overlap)):
            chunk_ids.append(f"{doc['id']}_chunk_{index}")
            chunk_texts.append(chunk)
            metadatas.append({"source": doc["id"], "chunk": index})
    if chunk_texts:
        vectors = model.encode(chunk_texts, normalize_embeddings=True, show_progress_bar=False).tolist()
        # Chroma has a per-batch limit in some hosted environments. Add safe batches.
        for start in range(0, len(chunk_texts), 400):
            stop = start + 400
            collection.add(
                ids=chunk_ids[start:stop],
                documents=chunk_texts[start:stop],
                embeddings=vectors[start:stop],
                metadatas=metadatas[start:stop],
            )
    return model, collection

def retrieve_campus_context(question, top_k=RAG_TOP_K_DEFAULT, chunk_size=RAG_CHUNK_SIZE_DEFAULT, chunk_overlap=RAG_CHUNK_OVERLAP_DEFAULT):
    """Embed a query and retrieve its Top-K nearest campus knowledge chunks."""
    if not RAG_AVAILABLE:
        return [], "RAG dependencies are not installed."
    try:
        model, collection = load_rag_index(int(chunk_size), int(chunk_overlap))
        if collection.count() == 0:
            return [], "The campus knowledge index is empty."
        query_vector = model.encode([question], normalize_embeddings=True).tolist()
        result = collection.query(
            query_embeddings=query_vector,
            n_results=min(max(1, int(top_k)), collection.count()),
            include=["documents", "distances", "metadatas"],
        )
        docs = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        retrieved = [
            {"text": text, "distance": float(distance), "source": meta.get("source", "campus_directory"), "chunk": meta.get("chunk", 0)}
            for text, distance, meta in zip(docs, distances, metas)
        ]
        return retrieved, None
    except Exception as exc:
        return [], f"RAG retrieval error: {exc}"

def generate_grounded_answer(question, context, route_description, api_key):
    """Ask Gemini to answer from retrieved campus context without inventing facts."""
    if not (GEMINI_AVAILABLE and api_key):
        return None
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""You are the Presidency University Campus Guide. Answer the student's question using only the retrieved campus context and route data below. If the answer is not supported, say the information is not available in the current campus knowledge base. Do not invent office hours, distances, landmarks, building details, or verified paths. Keep the answer concise.

Student question:
{question}

Retrieved campus context:
{context}

Route calculated by the local NetworkX graph (if any):
{route_description}

The route graph is an approximate prototype and must be verified on campus.
"""
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            contents=prompt,
        )
        return response.text
    except Exception:
        return None


def identify_campus_photo(uploaded_file, api_key):
    """Identify a campus place by comparing the uploaded photo with labelled reference pages."""
    if not (GEMINI_AVAILABLE and api_key):
        return {"error": "Photo identification requires a configured Gemini API key and google-genai package."}

    reference_dir = Path(__file__).resolve().parent / "campus_reference_pages"
    reference_paths = sorted(reference_dir.glob("reference_page_*.jpg"))
    if not reference_paths:
        return {"error": "The labelled campus reference images are missing. Upload the complete campus guide package."}

    try:
        from PIL import Image
        client = genai.Client(api_key=api_key)
        photo = Image.open(io.BytesIO(uploaded_file.getvalue())).convert("RGB")

        # Keep reference images compact while retaining the visible labels and scene details.
        reference_images = []
        for image_path in reference_paths:
            ref_image = Image.open(image_path).convert("RGB")
            ref_image.thumbnail((700, 1000))
            reference_images.append(ref_image)

        reference_labels = [
            "Office of controller examination", "Admin block", "Dean office of MBA department",
            "Nexus core", "Office of International Affairs", "Fee department", "Café", "ATM",
            "Library", "Medical room", "Computer lab", "Musical room", "DSA", "Amphitheater",
            "Cafetaria", "Auditorium", "M block", "Domino's", "Transport department",
            "Lassi house", "School of design", "Full stack development lab", "VR Studio",
            "AI centre of excellence", "Indoor games", "VJ Mart", "Office of registrar",
            "Department of civil", "School of law", "Dean office PSCS", "Gym", "Udaya Upahar",
            "Hatti Kaapi", "Media studies", "Crazy cups"
        ]
        prompt = f"""
You are a visual campus-location identifier for Presidency University, Yelahanka.
The first image is the student's newly uploaded campus photo. The remaining images are labelled
reference pages from the university's campus photo guide. Compare visible architecture, signs,
shop fronts, doors, corridors and surroundings. Use the printed captions and visible signboards.

Choose only one label from this exact reference list, or return Unknown:
{reference_labels}

Return ONLY JSON with keys: label, confidence, reason.
- label must be one exact label from the list or "Unknown".
- confidence must be a number from 0 to 1.
- reason must briefly state the visible evidence (such as sign text or matching features).
- Do not guess from generic corridors or similar-looking walls. If evidence is insufficient, use Unknown
  and a confidence below 0.5.
"""
        response = client.models.generate_content(
            model=os.getenv("GEMINI_VISION_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.8-flash")),
            contents=[prompt, photo, *reference_images],
            config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text)
        label = str(data.get("label", "Unknown")).strip()
        confidence = float(data.get("confidence", 0))
        confidence = max(0.0, min(1.0, confidence))
        reason = str(data.get("reason", "No visual evidence was provided."))

        # Map reference captions to nodes that already exist in this prototype's graph.
        label_to_location = {
            "Cafetaria": "Cafeteria",
            "Café": "Cafeteria",
            "Office of registrar": "Office of the Registrar",
            "DSA": "DSA Office",
            "Transport department": "Transport Office",
            "School of design": "School of Design",
            "School of law": "School of Law",
            "Media studies": "School of Media Studies",
            "Medical room": "Medical Room",
        }
        mapped_location = label_to_location.get(label)
        if mapped_location not in LOCATIONS:
            mapped_location = resolve_location(label)
        return {
            "label": label,
            "confidence": confidence,
            "reason": reason,
            "map_location": mapped_location,
        }
    except Exception as exc:
        return {"error": f"Could not identify this photo: {exc}"}


def shortest_route(start, destination):
    if start not in G or destination not in G:
        return None
    try:
        return nx.shortest_path(G, start, destination, weight="weight")
    except nx.NetworkXNoPath:
        return None

def route_text(route):
    if not route:
        return "I couldn't find a connected route. Try selecting both locations from the menus."
    if len(route) == 1:
        return f"You're already at **{route[0]}**."
    lines = [f"**{i}.** From **{a}**, follow the mapped campus path towards **{b}**."
             for i, (a, b) in enumerate(zip(route[:-1], route[1:]), 1)]
    return "\n\n".join(lines)

def make_map(route=None, start=None, destination=None, selected_category="All"):
    route = route or []
    fig = go.Figure()

    # Background path network
    for a, b in G.edges():
        xa, ya = G.nodes[a]["pos"]
        xb, yb = G.nodes[b]["pos"]
        fig.add_trace(go.Scatter(
            x=[xa, xb], y=[ya, yb], mode="lines",
            line=dict(color="#D9E2EC", width=3),
            hoverinfo="skip", showlegend=False
        ))

    # Highlight the selected route
    if len(route) > 1:
        rx, ry = zip(*(G.nodes[n]["pos"] for n in route))
        fig.add_trace(go.Scatter(
            x=rx, y=ry, mode="lines+markers",
            line=dict(color="#059669", width=7),
            marker=dict(size=10, color="#059669", line=dict(color="white", width=2)),
            name="Selected route", text=route, hovertemplate="%{text}<extra>Route</extra>"
        ))

    visible_nodes = []
    for name, data in G.nodes(data=True):
        if selected_category == "All" or data["category"] == selected_category:
            visible_nodes.append((name, data))
        elif name in route or name in [start, destination]:
            visible_nodes.append((name, data))

    xs, ys, names, colors, sizes, hovers = [], [], [], [], [], []
    for name, data in visible_nodes:
        x, y = data["pos"]
        xs.append(x); ys.append(y); names.append(name)
        hovers.append(f"<b>{name}</b><br>{data['category']}")
        if name == start:
            colors.append("#2563EB"); sizes.append(19)
        elif name == destination:
            colors.append("#DC2626"); sizes.append(19)
        elif name in route:
            colors.append("#059669"); sizes.append(13)
        else:
            colors.append("#64748B"); sizes.append(10)

    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text",
        marker=dict(size=sizes, color=colors, line=dict(color="white", width=2)),
        text=names, textposition="top center",
        textfont=dict(size=10, color="#243B53"),
        hovertext=hovers, hoverinfo="text", showlegend=False
    ))
    fig.update_layout(
        height=680, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="white", plot_bgcolor="white",
        xaxis=dict(visible=False, range=[10, 96], fixedrange=True),
        yaxis=dict(visible=False, range=[0, 104], fixedrange=True, scaleanchor="x"),
        showlegend=False,
    )
    return fig

# ------------------------- DESIGN -------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #F3F6F9; color: #102A43; }
.block-container { padding-top: 1.2rem; max-width: 1600px; }
.hero { background: linear-gradient(115deg,#102A43 0%,#164E63 52%,#0F766E 100%);
        padding: 1.65rem 1.8rem; border-radius: 20px; color: white; margin-bottom: 1.2rem;
        box-shadow: 0 10px 30px rgba(16,42,67,.12); }
.hero h1 { color:white; font-size:2rem; margin:0; letter-spacing:-.03em; }
.hero p { color:#D9F4EE; margin:.45rem 0 0 0; }
.card { background:white; padding:1.1rem 1.25rem; border-radius:16px;
        border:1px solid #E3EAF0; }
div[data-testid="stMetric"] { background:white; border:1px solid #E3EAF0;
    padding:12px; border-radius:14px; }
div.stButton > button { border-radius: 10px; font-weight:600; }
[data-testid="stChatMessage"] { background:white; border:1px solid #E3EAF0; border-radius:14px; }
</style>
<div class="hero">
  <h1>🧭 Presidency Campus Guide</h1>
  <p>Ask naturally. Get clear written directions with a visual route map.</p>
</div>
""", unsafe_allow_html=True)

if "start" not in st.session_state:
    st.session_state.start = "University Entrance"
if "destination" not in st.session_state:
    st.session_state.destination = "Cafeteria"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "active_route" not in st.session_state:
    st.session_state.active_route = shortest_route(st.session_state.start, st.session_state.destination)

# Widget values must be set BEFORE the selectboxes are created.
# Chatbot/quick-button actions place desired values in these pending keys,
# which are applied at the beginning of the next Streamlit rerun.
if "start_selector" not in st.session_state:
    st.session_state.start_selector = st.session_state.start
if "destination_selector" not in st.session_state:
    st.session_state.destination_selector = st.session_state.destination
if "_pending_start_selector" in st.session_state:
    st.session_state.start_selector = st.session_state.pop("_pending_start_selector")
if "_pending_destination_selector" in st.session_state:
    st.session_state.destination_selector = st.session_state.pop("_pending_destination_selector")

with st.sidebar:
    st.markdown("## 🗺️ Navigation")
    st.caption("PRESIDENCY UNIVERSITY · YELAHANKA")
    all_locations = list(LOCATIONS.keys())
    start_choice = st.selectbox(
        "Starting point", all_locations, key="start_selector"
    )
    dest_choice = st.selectbox(
        "Destination", all_locations, key="destination_selector"
    )

    # Keep the app's route variables synchronized with the visible widgets.
    st.session_state.start = start_choice
    st.session_state.destination = dest_choice

    if st.button("Show route", type="primary", use_container_width=True):
        st.session_state.start = start_choice
        st.session_state.destination = dest_choice
        st.session_state.active_route = shortest_route(start_choice, dest_choice)
    st.markdown("---")
    st.markdown("**Quick destinations**")
    for label, dest in [
        ("🍽️ Cafeteria", "Cafeteria"),
        ("🧾 Admission Office", "Admission Office"),
        ("🎓 School of Engineering", "School of Engineering"),
        ("☕ Hatti Kaapi", "Hatti Kaapi"),
        ("🚑 Medical Room", "Medical Room"),
    ]:
        if st.button(label, use_container_width=True):
            st.session_state.destination = dest
            st.session_state._pending_destination_selector = dest
            st.session_state.active_route = shortest_route(st.session_state.start, dest)
            st.rerun()
    st.markdown("---")
    st.markdown("**RAG knowledge search**")
    rag_top_k = st.slider("Top-K retrieved chunks", min_value=1, max_value=8, value=RAG_TOP_K_DEFAULT, key="rag_top_k")
    rag_chunk_size = st.slider("Chunk size (words)", min_value=100, max_value=800, value=RAG_CHUNK_SIZE_DEFAULT, step=50, key="rag_chunk_size")
    rag_chunk_overlap = st.slider("Chunk overlap (words)", min_value=0, max_value=200, value=RAG_CHUNK_OVERLAP_DEFAULT, step=10, key="rag_chunk_overlap")
    st.caption("RAG: " + ("ChromaDB + sentence embeddings available" if RAG_AVAILABLE else "Install chromadb and sentence-transformers"))
    st.markdown("---")
    st.caption("Map geometry and paths are approximate and need campus verification.")

map_col, chat_col = st.columns([1.15, 1], gap="large")

with map_col:
    top1, top2 = st.columns([1.4, 1])
    with top1:
        st.markdown("### Interactive campus map")
    with top2:
        categories = ["All"] + sorted({d[2] for d in LOCATIONS.values()})
        category = st.selectbox("Filter locations", categories, label_visibility="collapsed")
    st.plotly_chart(
        make_map(st.session_state.active_route, st.session_state.start,
                 st.session_state.destination, category),
        use_container_width=True,
        config={"displayModeBar": False, "scrollZoom": False},
    )
    st.markdown(
        '<div class="card"><b>Map key</b> &nbsp; '
        '<span style="color:#2563EB">● Start</span> &nbsp; '
        '<span style="color:#DC2626">● Destination</span> &nbsp; '
        '<span style="color:#059669">━ Route</span><br>'
        '<span style="color:#64748B;font-size:.85rem">Schematic campus layout, not a surveyed or GPS-accurate map.</span></div>',
        unsafe_allow_html=True,
    )

with chat_col:
    st.markdown("### Campus assistant")
    st.caption("Ask about blocks, offices, food spots and campus facilities.")
    # Streamlit Community Cloud secrets first; environment variable fallback for local/Colab use.
    try:
        configured_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        configured_key = ""
    api_key = (configured_key or os.getenv("GEMINI_API_KEY", "")).strip()
    if api_key and GEMINI_AVAILABLE:
        st.caption("✨ Natural-language AI enabled")
    else:
        st.caption("⚡ Smart local mode enabled · add a Gemini API key for more flexible questions")
    st.caption("📚 RAG retrieval: " + ("enabled" if RAG_AVAILABLE else "dependencies missing"))

    # Photo-based location identification, using the user's labelled campus reference PDF.
    with st.expander("📷 Identify location from a photo", expanded=False):
        st.caption("Upload a photo taken on campus. Gemini Vision compares it with the labelled campus reference images.")
        campus_photo = st.file_uploader(
            "Upload campus photo", type=["jpg", "jpeg", "png", "webp"],
            key="campus_location_photo"
        )
        if campus_photo is not None:
            st.image(campus_photo, caption="Uploaded campus photo", use_container_width=True)
            if st.button("Identify location", key="identify_campus_photo", type="primary"):
                with st.spinner("Comparing your photo with the labelled campus references..."):
                    st.session_state["campus_photo_result"] = identify_campus_photo(campus_photo, api_key)
            photo_result = st.session_state.get("campus_photo_result")
            if photo_result:
                if photo_result.get("error"):
                    st.error(photo_result["error"])
                else:
                    st.markdown(f"**Identified place:** {photo_result['label']}")
                    st.caption(f"Confidence: {photo_result['confidence']:.0%}")
                    st.write(photo_result.get("reason", ""))
                    if photo_result.get("map_location") and photo_result["confidence"] >= 0.60:
                        st.success(f"Available in the campus route map as **{photo_result['map_location']}**.")
                        photo_role = st.radio(
                            "Use this photo location as", ["Starting point", "Destination"],
                            horizontal=True, key="campus_photo_role"
                        )
                        if st.button("Use identified location", key="apply_campus_photo_location"):
                            selected_place = photo_result["map_location"]
                            if photo_role == "Starting point":
                                st.session_state.start = selected_place
                                st.session_state["_pending_start_selector"] = selected_place
                            else:
                                st.session_state.destination = selected_place
                                st.session_state["_pending_destination_selector"] = selected_place
                            st.session_state.active_route = shortest_route(
                                st.session_state.start, st.session_state.destination
                            )
                            st.rerun()
                    elif photo_result["label"] != "Unknown":
                        st.warning("This place is recognised from the reference guide, but it is not yet a routable node in the current campus map. Its map position and walking connections must be added first.")
                    else:
                        st.warning("The photo could not be matched confidently. Try a clearer photo showing the signboard or a distinctive entrance.")
        elif not (GEMINI_AVAILABLE and api_key):
            st.info("Configure GEMINI_API_KEY and install google-genai to enable photo identification.")

    for message in st.session_state.chat_history[-8:]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # Show the visual route image directly inside the chatbot response.
            if message.get("route"):
                st.plotly_chart(
                    make_map(
                        message["route"],
                        message.get("start"),
                        message.get("destination"),
                        "All",
                    ),
                    use_container_width=True,
                    config={"displayModeBar": False},
                    key=f"chat_route_{message.get('message_id', 'old')}",
                )

    question = st.chat_input("Try: How do I get from U-Block to the cafeteria?")
    # Clear the submission guard on ordinary reruns. This still allows the same
    # exact question to be submitted again later, but prevents a live submitted
    # value from being processed twice during an immediate rerun.
    if not question:
        st.session_state.pop("_last_processed_question", None)
    if question and question != st.session_state.get("_last_processed_question"):
        st.session_state["_last_processed_question"] = question
        st.session_state.chat_history.append({"role": "user", "content": question})
        # Prefer deterministic local parsing for explicit routes. This avoids API
        # delays or model mistakes when a question clearly names both endpoints.
        parsed = parse_question_rules(question, st.session_state.start)
        if parsed.get("intent") == "unknown" and api_key:
            ai_parsed = parse_question_gemini(question, st.session_state.start, api_key)
            if ai_parsed:
                parsed = ai_parsed

        intent = parsed.get("intent", "unknown")
        chosen_start = parsed.get("start") if parsed.get("start") in LOCATIONS else st.session_state.start
        chosen_dest = parsed.get("destination")
        answer = ""

        # Retrieve relevant campus chunks for every question using embeddings + ChromaDB.
        with st.spinner("Searching the campus knowledge base..."):
            retrieved_docs, rag_error = retrieve_campus_context(
                question, top_k=rag_top_k, chunk_size=rag_chunk_size, chunk_overlap=rag_chunk_overlap
            )
        rag_context = "\n\n".join(
            f"[{item['source']} | chunk {item['chunk']}] {item['text']}" for item in retrieved_docs
        )

        if intent == "food":
            options = parsed.get("suggestions") or [
                name for name, (_, _, cat) in LOCATIONS.items() if cat == "Food"
            ]
            answer = "Here are the food and drink locations in this prototype:\n\n"
            answer += "\n".join(f"- **{place}**" for place in options if place in LOCATIONS)
            answer += "\n\nChoose one from the Destination menu to display a route."
        elif intent in ("route", "find_place") and chosen_dest:
            if intent == "find_place":
                answer = f"**{chosen_dest}** is listed as a campus {LOCATIONS[chosen_dest][2].lower()} location.\n\n"
                answer += f"I'll show a route from your selected starting point, **{chosen_start}**."
            route = shortest_route(chosen_start, chosen_dest)
            st.session_state.start = chosen_start
            st.session_state.destination = chosen_dest
            # Apply widget values on the next rerun before selectboxes are rendered.
            st.session_state["_pending_start_selector"] = chosen_start
            st.session_state["_pending_destination_selector"] = chosen_dest
            st.session_state.active_route = route
            answer = f"**Starting point:** {chosen_start}\n\n**Destination:** {chosen_dest}\n\n" + answer
            if route:
                if answer:
                    answer += "\n\n### Suggested route\n\n"
                else:
                    answer = f"### Route: {chosen_start} → {chosen_dest}\n\n"
                answer += route_text(route)
                answer += "\n\n*Please verify this prototype route with campus signage; the path network is approximate.*"
            else:
                answer += "\n\nI couldn't find a connected path for those locations in the current prototype."
        elif intent == "help":
            answer = "I can help find campus blocks, academic schools, offices, food spots and facilities.\n\n"
            answer += "Try **'How do I get from U-Block to H-Block?'**, **'Where is the admission office?'**, or **'Where can I get coffee?'**"
        else:
            answer = "I can help with campus navigation. Please mention a place name, such as **cafeteria**, **H-Block**, **admission office**, **Subway**, or ask **'from U-Block to H-Block'**."
        # Gemini may phrase an answer, but it receives only retrieved context and
        # the route already calculated by NetworkX; it never creates the route.
        route_for_prompt = st.session_state.active_route
        route_description = "No route calculated."
        if route_for_prompt:
            route_description = " -> ".join(route_for_prompt)
        if rag_context and api_key:
            grounded = generate_grounded_answer(question, rag_context, route_description, api_key)
            if grounded:
                if intent in ("route", "find_place") and chosen_dest:
                    answer = grounded + "\n\n---\n**Route calculated by the campus graph:**\n\n" + route_text(route_for_prompt)
                else:
                    answer = grounded
        if retrieved_docs:
            answer += "\n\n**Retrieved campus sources:** " + ", ".join(
                f"`{item['source']}`" for item in retrieved_docs
            )
        elif rag_error:
            answer += f"\n\n*Knowledge retrieval unavailable: {rag_error}*"

        assistant_message = {"role": "assistant", "content": answer}
        # Attach the calculated route to the response so the map appears with the text.
        if intent in ("route", "find_place") and chosen_dest and st.session_state.active_route:
            assistant_message["route"] = st.session_state.active_route
            assistant_message["start"] = st.session_state.start
            assistant_message["destination"] = st.session_state.destination
            assistant_message["message_id"] = len(st.session_state.chat_history)
        st.session_state.chat_history.append(assistant_message)
        st.rerun()

    route = st.session_state.active_route
    st.markdown("---")
    st.markdown("#### Current trip")
    metric1, metric2 = st.columns(2)
    metric1.metric("Route segments", max(len(route) - 1, 0) if route else "—")
    metric2.metric("Destination type", LOCATIONS[st.session_state.destination][2])
    st.markdown(f"**{st.session_state.start}**  →  **{st.session_state.destination}**")
    if route:
        for line in route_text(route).split("\n\n"):
            st.markdown(line)

st.markdown("---")
with st.expander("About this prototype and its accuracy"):
    st.write(
        "This hackathon prototype combines the supplied campus maps with a manually drafted graph of "
        "locations and connections. The map is schematic, coordinates are not GPS coordinates, and the "
        "connections have not yet been verified on the ground. Do not rely on it for emergency navigation. "
        "Before presenting route accuracy as a feature, walk the paths and correct the LOCATIONS and EDGES "
        "data near the top of this Python file."
    )
    st.write(
        "RAG: campus directory facts are split into overlapping chunks, embedded with "
        "sentence-transformers/all-MiniLM-L6-v2, stored in ChromaDB, and retrieved with Top-K similarity search. "
        "The initial knowledge base is generated from the locations and draft graph in this app; it does not "
        "contain official office hours or independently verified campus facts. Gemini can phrase answers from "
        "retrieved context; photo identification compares uploads with the labelled reference pages; NetworkX calculates routes."
    )
