from __future__ import annotations

from pathlib import Path

from teaagent.code_analysis._treesitter import (
    CodeRelation,
    extract_tree_sitter_relations,
)
from teaagent.graph_rag import GraphEdge, KnowledgeGraph
from teaagent.rag import Document


def ingest_code_relations_to_graph(
    path: str,
    graph: KnowledgeGraph,
    *,
    doc_id: str | None = None,
    source: str = 'code',
) -> list[CodeRelation]:
    file_path = Path(path)
    resolved_doc_id = doc_id or str(file_path)
    if not any(doc.doc_id == resolved_doc_id for doc in graph.all_documents()):
        graph.add_document(
            Document(
                doc_id=resolved_doc_id,
                text=file_path.read_text(encoding='utf-8'),
                source=source,
                metadata={'path': str(file_path)},
            )
        )
    relations = extract_tree_sitter_relations(str(file_path))
    for relation in relations:
        graph.add_edge(
            GraphEdge(
                source=relation.source,
                relation=relation.relation,
                target=relation.target,
                document_ids=(resolved_doc_id,),
            )
        )
    return relations
