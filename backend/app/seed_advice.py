"""Advice for the PlantVillage classes that are NOT in seed.py (apple, grape, cherry, peach, citrus, ...).

IMPORTANT: this text is general extension-style guidance written for a demo. It has NOT been reviewed by an
agronomist. Have a local agriculture officer review it, and check which products are registered in your
country, before real farmers rely on it. The product label always wins.

These crops are not in the price tables, so their rows have no crop link (crop_id = NULL). The crop is part of
the display name instead, e.g. "Grape: Black rot".

TO CHANGE: edit a row, or add one. `label` must match a class name in models/labels.json.
Row format: label -> (display name, symptoms, organic treatment, chemical treatment, prevention)
"""

_LABEL = "Follow the product label and use only products registered for this crop in your area."
_HEALTHY_TIP = "Keep monitoring weekly. Remove fallen leaves and keep the canopy open for airflow."

EXTRA_DISEASES = {
    "Apple___Apple_scab": ("Apple: Scab",
        "Olive-green to dark velvety spots on leaves and fruit; fruit becomes scabby and cracked; leaves may drop early.",
        "Rake and destroy fallen leaves; prune for airflow; sulphur or copper sprays at bud break as allowed locally.",
        "Protectant fungicides (for example captan or mancozeb) from bud break through petal fall. " + _LABEL,
        "Plant resistant varieties, remove leaf litter in autumn, avoid overhead irrigation."),
    "Apple___Black_rot": ("Apple: Black rot",
        "Purple-edged brown spots on leaves ('frog-eye'); rotting fruit with dark rings; cankers on branches.",
        "Prune out cankers and mummified fruit and destroy them; keep trees well pruned.",
        "Protectant fungicides during the growing season. " + _LABEL,
        "Remove dead wood and mummies, avoid wounding trees, keep trees vigorous."),
    "Apple___Cedar_apple_rust": ("Apple: Cedar apple rust",
        "Bright yellow-orange spots on leaves, later with small tube-like structures underneath; fruit may be deformed.",
        "Remove nearby juniper or cedar hosts where possible; remove badly affected leaves.",
        "Protectant fungicides from pink bud stage through early summer. " + _LABEL,
        "Plant resistant varieties and keep apples away from juniper or cedar trees."),
    "Apple___healthy": ("Healthy apple leaf", "", "", "", _HEALTHY_TIP),
    "Blueberry___healthy": ("Healthy blueberry leaf", "", "", "", _HEALTHY_TIP),
    "Cherry_(including_sour)___Powdery_mildew": ("Cherry: Powdery mildew",
        "White powdery coating on young leaves; leaves curl and may distort; fruit can be affected.",
        "Prune to open the canopy; sulphur sprays early in the season if allowed locally.",
        "Fungicides registered for powdery mildew on cherry. " + _LABEL,
        "Prune for airflow, avoid excess nitrogen, and choose resistant varieties."),
    "Cherry_(including_sour)___healthy": ("Healthy cherry leaf", "", "", "", _HEALTHY_TIP),
    "Grape___Black_rot": ("Grape: Black rot",
        "Small brown circular leaf spots with dark edges; fruit shrivels into hard black 'mummies'.",
        "Remove and destroy mummified berries and infected leaves; keep the canopy open.",
        "Protectant fungicides from early shoot growth through fruit set. " + _LABEL,
        "Clean up mummies in winter, prune for airflow, and train vines to dry quickly."),
    "Grape___Esca_(Black_Measles)": ("Grape: Esca (black measles)",
        "Yellow or brown 'tiger-stripe' patches between the leaf veins; dark spots on berries; vines may die back.",
        "Prune out dead and diseased wood in dry weather and destroy it; protect pruning wounds.",
        "No fully effective cure. Wound sealants or protectants may reduce new infections. " + _LABEL,
        "Prune only in dry weather, disinfect tools, and avoid large pruning wounds."),
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": ("Grape: Leaf blight (Isariopsis leaf spot)",
        "Dark brown to black irregular spots on leaves, often with a yellow edge; heavily affected leaves dry and fall.",
        "Remove and destroy affected leaves; improve airflow by pruning and training the canopy.",
        "Protectant fungicides such as copper-based or mancozeb products. " + _LABEL,
        "Avoid overhead irrigation, clear fallen leaves, and keep the canopy open."),
    "Grape___healthy": ("Healthy grape leaf", "", "", "", _HEALTHY_TIP),
    "Orange___Haunglongbing_(Citrus_greening)": ("Citrus: Greening (Huanglongbing)",
        "Yellow blotchy mottling on leaves, lopsided small bitter fruit, twig dieback; spread by a small insect (psyllid).",
        "Remove and destroy infected trees to protect others; control the psyllid; use only certified disease-free plants.",
        "There is no cure. Insecticides against the psyllid vector may slow spread. " + _LABEL,
        "Plant certified clean nursery stock, scout for psyllids, and report suspected cases to your agriculture officer."),
    "Peach___Bacterial_spot": ("Peach: Bacterial spot",
        "Small angular dark spots on leaves that may fall out, leaving a shot-hole look; spots and cracks on fruit.",
        "Prune for airflow; avoid working in wet orchards; copper sprays in the dormant season as allowed.",
        "Copper-based or other bactericides registered for peach. " + _LABEL,
        "Plant tolerant varieties, avoid excess nitrogen, and avoid overhead irrigation."),
    "Peach___healthy": ("Healthy peach leaf", "", "", "", _HEALTHY_TIP),
    "Raspberry___healthy": ("Healthy raspberry leaf", "", "", "", _HEALTHY_TIP),
    "Soybean___healthy": ("Healthy soybean leaf", "", "", "", _HEALTHY_TIP),
    "Squash___Powdery_mildew": ("Squash: Powdery mildew",
        "White powdery patches on the upper side of leaves; leaves turn yellow, then brown and die.",
        "Remove badly affected leaves; spray a diluted milk or potassium bicarbonate solution, or sulphur, where allowed.",
        "Fungicides registered for powdery mildew on squash. " + _LABEL,
        "Plant resistant varieties, space plants for airflow, and avoid overcrowding."),
    "Strawberry___Leaf_scorch": ("Strawberry: Leaf scorch",
        "Many small purple spots on leaves that merge into scorched-looking brown patches; leaves may curl and dry.",
        "Remove infected leaves after harvest; keep beds well spaced and free of weeds.",
        "Protectant fungicides if severe. " + _LABEL,
        "Use clean planting stock, avoid overhead irrigation, and renovate beds after harvest."),
    "Strawberry___healthy": ("Healthy strawberry leaf", "", "", "", _HEALTHY_TIP),
}
