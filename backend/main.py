from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pyscf import gto, mcscf
import numpy as np
from typing import Optional
import struct

app = FastAPI(title="PySCF MCSCF Orbital Visualization API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Molecule presets ──────────────────────────────────────────────
MOLECULE_PRESETS = {
    "water": {
        "name": "Water (H₂O)",
        "atom": "O 0.0 0.0 0.0; H 0.0 -0.757 0.587; H 0.0 0.757 0.587",
        "basis": "6-31g",
        "ncas": 4, "nelecas": 4,
    },
    "formaldehyde": {
        "name": "Formaldehyde (CH₂O)",
        "atom": "C 0.0 0.0 0.0; O 0.0 0.0 1.203; H 0.0 0.934 -0.587; H 0.0 -0.934 -0.587",
        "basis": "6-31g",
        "ncas": 4, "nelecas": 4,
    },
    "ethylene": {
        "name": "Ethylene (C₂H₄)",
        "atom": "C 0.0 0.0 0.6695; C 0.0 0.0 -0.6695; H 0.0 0.923 1.2321; H 0.0 -0.923 1.2321; H 0.0 0.923 -1.2321; H 0.0 -0.923 -1.2321",
        "basis": "6-31g",
        "ncas": 2, "nelecas": 2,
    },
    "nitrogen": {
        "name": "Nitrogen (N₂)",
        "atom": "N 0.0 0.0 0.0; N 0.0 0.0 1.0977",
        "basis": "6-31g",
        "ncas": 6, "nelecas": 6,
    },
    "hydrogen_fluoride": {
        "name": "Hydrogen Fluoride (HF)",
        "atom": "H 0.0 0.0 0.0; F 0.0 0.0 0.917",
        "basis": "6-31g",
        "ncas": 4, "nelecas": 4,
    },
    "lithium_hydride": {
        "name": "Lithium Hydride (LiH)",
        "atom": "Li 0.0 0.0 0.0; H 0.0 0.0 1.595",
        "basis": "6-31g",
        "ncas": 2, "nelecas": 2,
    },
}

# Cache for MCSCF results keyed by molecule id
_cached_mcscf: dict = {}


def get_mcscf_results(molecule_id: str = "water"):
    """Get cached MCSCF results for a given molecule preset"""
    if molecule_id not in _cached_mcscf:
        preset = MOLECULE_PRESETS.get(molecule_id)
        if preset is None:
            raise ValueError(f"Unknown molecule: {molecule_id}")

        mol = gto.M(atom=preset["atom"], basis=preset["basis"], verbose=0)
        mf = mol.RHF().run()
        mc = mcscf.CASSCF(mf, preset["ncas"], preset["nelecas"]).run()
        natorb_coeff, ci, natorb_occ = mcscf.casci.cas_natorb(mc)
        _cached_mcscf[molecule_id] = {
            "mol": mol,
            "mc": mc,
            "natorbs": natorb_coeff,
            "occupations": natorb_occ,
            "energy": float(mc.e_tot),
        }
    return _cached_mcscf[molecule_id]


def get_grid_bounds(mol, margin_angstrom=5.0):
    """Calculate grid bounds with specified margin in Angstroms"""
    coords = mol.atom_coords()
    min_coords = np.min(coords, axis=0) - margin_angstrom
    max_coords = np.max(coords, axis=0) + margin_angstrom
    return min_coords, max_coords


def evaluate_orbital_on_grid(mol, mo_coeff, grid_points):
    """Evaluate molecular orbital on grid using mol.eval_gto"""
    ao_value = mol.eval_gto('GTOval_sph', grid_points)
    mo_value = np.dot(ao_value, mo_coeff)
    return mo_value


def generate_orbital_labels(mol, mo_coeffs, occupations):
    """Generate human-readable labels for molecular orbitals based on AO character."""
    ao_labels = mol.ao_labels(fmt=False)  # list of (atom_idx, element, orbital_type, m_label)
    n_orbitals = mo_coeffs.shape[1]
    labels = []

    # Angular momentum sublabels
    l_names = {0: 's', 1: 'p', 2: 'd', 3: 'f'}

    for i in range(n_orbitals):
        coeffs = mo_coeffs[:, i]
        weights = coeffs ** 2
        total_weight = np.sum(weights)
        if total_weight < 1e-10:
            labels.append(f"MO {i+1}")
            continue

        # Group weights by atom and by angular momentum
        atom_weights = {}  # atom_label -> total weight
        atom_l_weights = {}  # (atom_label, l) -> total weight
        atom_l_details = {}  # (atom_label, l) -> [(m_label, weight), ...]

        for j, (atom_idx, element, orb_type, m_label) in enumerate(ao_labels):
            w = weights[j]
            atom_label = f"{element}{atom_idx+1}" if sum(1 for a in ao_labels if a[1] == element) > len(mol.atom_coords()) // 2 else element

            # Determine angular momentum from orbital type string
            # orb_type is like '1s', '2s', '2p', '3d', etc.
            l_char = orb_type[-1] if orb_type else 's'
            l_num = {'s': 0, 'p': 1, 'd': 2, 'f': 3}.get(l_char, 0)
            n_quantum = orb_type[:-1] if len(orb_type) > 1 else ''

            atom_weights[atom_label] = atom_weights.get(atom_label, 0) + w

            key = (atom_label, l_char, n_quantum)
            atom_l_weights[key] = atom_l_weights.get(key, 0) + w

            if key not in atom_l_details:
                atom_l_details[key] = []
            atom_l_details[key].append((m_label, w))

        # Sort atoms by weight
        sorted_atoms = sorted(atom_weights.items(), key=lambda x: -x[1])

        # Sort atom+l contributions by weight
        sorted_al = sorted(atom_l_weights.items(), key=lambda x: -x[1])

        # Build label from top contributions
        occ = occupations[i] if i < len(occupations) else 0
        parts = []
        cumulative = 0
        for (atom_label, l_char, n_q), w in sorted_al:
            frac = w / total_weight
            if frac < 0.10 and len(parts) >= 1:
                break
            if len(parts) >= 2:
                break
            shell_str = f"{n_q}{l_char}" if n_q else l_char
            parts.append(f"{atom_label} {shell_str}")
            cumulative += frac

        # Classify bonding character
        # If significant weight on multiple atoms, it's a bonding/antibonding orbital
        multi_atom = len([a for a, w in sorted_atoms if w / total_weight > 0.15]) > 1
        top_frac = sorted_atoms[0][1] / total_weight if sorted_atoms else 0

        if multi_atom:
            # Check if antibonding (look for sign changes between atom contributions)
            # Simple heuristic: find dominant AO on each major atom and check sign
            major_atoms = [(a, w) for a, w in sorted_atoms if w / total_weight > 0.15]
            atom_signs = {}
            for atom_label, _ in major_atoms:
                # Get the coefficient with the largest magnitude for this atom
                max_coeff = 0
                for j, (atom_idx, element, orb_type, m_label) in enumerate(ao_labels):
                    a_lbl = f"{element}{atom_idx+1}" if sum(1 for a in ao_labels if a[1] == element) > len(mol.atom_coords()) // 2 else element
                    if a_lbl == atom_label and abs(coeffs[j]) > abs(max_coeff):
                        max_coeff = coeffs[j]
                atom_signs[atom_label] = np.sign(max_coeff)

            signs = list(atom_signs.values())
            is_antibonding = len(set(signs)) > 1

            atom_names = [a for a, _ in major_atoms[:2]]
            bond_label = "-".join(atom_names)
            if is_antibonding:
                label = f"σ*({bond_label})"
            else:
                label = f"σ({bond_label})"
        else:
            label = parts[0] if parts else f"MO {i+1}"

        labels.append(label)

    return labels


@app.get("/")
async def root():
    return {"message": "PySCF MCSCF Orbital Visualization API"}


@app.get("/api/molecules")
async def list_molecules():
    """List all available molecule presets"""
    return [
        {"id": mid, "name": preset["name"]}
        for mid, preset in MOLECULE_PRESETS.items()
    ]


@app.get("/api/orbital/{orbital_index}")
async def get_orbital_data(
    orbital_index: int = 0,
    grid_size: int = 64,
    margin: float = 5.0,
    isovalue: Optional[float] = None,
    molecule: str = "water",
):
    """
    Get orbital data as Float32 binary buffer
    """
    results = get_mcscf_results(molecule)
    mol = results["mol"]
    natorbs = results["natorbs"]
    
    if orbital_index >= natorbs.shape[1]:
        return Response(
            content=f"Orbital index {orbital_index} out of range",
            status_code=400
        )
    
    # Calculate grid bounds
    min_coords, max_coords = get_grid_bounds(mol, margin)
    
    # Create 3D grid
    x = np.linspace(min_coords[0], max_coords[0], grid_size)
    y = np.linspace(min_coords[1], max_coords[1], grid_size)
    z = np.linspace(min_coords[2], max_coords[2], grid_size)
    
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    grid_points = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
    
    # Evaluate orbital on grid
    mo_coeff = natorbs[:, orbital_index]
    orbital_values = evaluate_orbital_on_grid(mol, mo_coeff, grid_points)
    orbital_grid = orbital_values.reshape(grid_size, grid_size, grid_size)
    
    # Convert to Float32 and create binary buffer
    orbital_float32 = orbital_grid.astype(np.float32)
    binary_data = orbital_float32.tobytes()
    
    # Create metadata header (grid dimensions and bounds)
    header = struct.pack('3i6f', 
                        grid_size, grid_size, grid_size,
                        min_coords[0], min_coords[1], min_coords[2],
                        max_coords[0], max_coords[1], max_coords[2])
    
    return Response(
        content=header + binary_data,
        media_type="application/octet-stream",
        headers={
            "X-Grid-Size": str(grid_size),
            "X-Min-Coords": f"{min_coords[0]},{min_coords[1]},{min_coords[2]}",
            "X-Max-Coords": f"{max_coords[0]},{max_coords[1]},{max_coords[2]}"
        }
    )


@app.get("/api/molecule/info")
async def get_molecule_info(molecule: str = "water"):
    """Get information about the molecule"""
    results = get_mcscf_results(molecule)
    mol = results["mol"]
    
    orbital_labels = generate_orbital_labels(
        mol, results["natorbs"], results["occupations"]
    )

    return {
        "atoms": [
            {"element": atom[0], "coords": atom[1].tolist() if hasattr(atom[1], 'tolist') else list(atom[1])}
            for atom in mol._atom
        ],
        "num_orbitals": results["natorbs"].shape[1],
        "basis": mol.basis,
        "occupations": results["occupations"].tolist(),
        "orbital_labels": orbital_labels,
        "energy": results["energy"],
    }


@app.get("/api/orbitals/batch")
async def get_orbital_batch(
    indices: str = "0,1,2,3",
    grid_size: int = 48,
    margin: float = 5.0,
    molecule: str = "water",
):
    """
    Get multiple orbitals in one request as concatenated binary data.
    """
    results = get_mcscf_results(molecule)
    mol = results["mol"]
    natorbs = results["natorbs"]
    
    orbital_indices = [int(i.strip()) for i in indices.split(",")]
    
    # Validate indices
    for idx in orbital_indices:
        if idx < 0 or idx >= natorbs.shape[1]:
            return Response(
                content=f"Orbital index {idx} out of range (0-{natorbs.shape[1]-1})",
                status_code=400
            )
    
    min_coords, max_coords = get_grid_bounds(mol, margin)
    
    x = np.linspace(min_coords[0], max_coords[0], grid_size)
    y = np.linspace(min_coords[1], max_coords[1], grid_size)
    z = np.linspace(min_coords[2], max_coords[2], grid_size)
    xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
    grid_points = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
    
    num_orbs = len(orbital_indices)
    # Header: num_orbitals, gx, gy, gz, minX, minY, minZ, maxX, maxY, maxZ, indices...
    header = struct.pack(
        f'<{4 + num_orbs}i6f',
        num_orbs, grid_size, grid_size, grid_size,
        *orbital_indices,
        float(min_coords[0]), float(min_coords[1]), float(min_coords[2]),
        float(max_coords[0]), float(max_coords[1]), float(max_coords[2]),
    )
    
    all_data = bytearray(header)
    for idx in orbital_indices:
        mo_coeff = natorbs[:, idx]
        orbital_values = evaluate_orbital_on_grid(mol, mo_coeff, grid_points)
        orbital_grid = orbital_values.reshape(grid_size, grid_size, grid_size)
        all_data.extend(orbital_grid.astype(np.float32).tobytes())
    
    return Response(
        content=bytes(all_data),
        media_type="application/octet-stream"
    )
