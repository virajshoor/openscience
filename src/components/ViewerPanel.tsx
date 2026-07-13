import { useSession } from "../stores/session";
import ProteinViewer from "./viewers/ProteinViewer";
import GenomeViewer from "./viewers/GenomeViewer";
import ChemViewer from "./viewers/ChemViewer";

export default function ViewerPanel() {
  const viewer = useSession((s) => s.viewer);

  if (!viewer) {
    return (
      <div className="viewer-empty">
        <div className="viewer-empty-icon">🧪</div>
        <div>
          Scientific artifacts appear here.<br />
          <span style={{ color: "#4b5563", fontSize: 12 }}>
            Ask the assistant to fetch a protein structure, sequence, or compound.
          </span>
        </div>
      </div>
    );
  }

  if (viewer.type === "protein") return <ProteinViewer src={viewer.src} label={viewer.label} />;
  if (viewer.type === "genome") return <GenomeViewer src={viewer.src} label={viewer.label} />;
  if (viewer.type === "chem") return <ChemViewer smiles={viewer.smiles} label={viewer.label} />;

  return <div className="viewer-empty">Unsupported viewer</div>;
}