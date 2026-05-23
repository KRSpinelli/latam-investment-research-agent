"""
Demo: ingest Cooxupé data into Senso and run a sample search.

Data sources (fetched by Nimble or manually extracted):
  - InfoMoney article: 2024 harvest outlook and investment plans
  - Sustainability Report 2025/2024 (English edition)

Run via:
    SENSO_API_KEY=<your_key> uv run python -m \
        latam_investment_research_agent.agents.semantic_storage.demo_cooxupe
"""

from __future__ import annotations

import asyncio

from .client import SensoClient
from .ingest import FilingMetadata, ingest_filing
from .kb_scaffold import scaffold_kb
from .search import search_for_brief

# ---------------------------------------------------------------------------
# Sample text from Nimble extraction (InfoMoney, May 2024)
# ---------------------------------------------------------------------------

INFOMONEY_ARTICLE = """
Cooxupé se prepara para receber 7 milhões de sacas de café em 2024

A Cooperativa Regional dos Cafeicultores em Guaxupé Ltda (Cooxupé), localizada em Minas Gerais,
está se preparando para receber um volume maior de seus cooperados durante a safra de 2024,
que se inicia entre maio e junho.

A cooperativa projeta receber 7 milhões de sacas de café neste ano, representando um aumento
de 500.000 sacas em relação a 2023 — crescimento de 7,7% ano a ano. Segundo o presidente
Carlos Augusto Rodrigues de Melo: "A safra de 2024 será muito semelhante à de 2023. Entre
as regiões onde atuamos, Matas de Minas deverá apresentar o maior crescimento, pois é a
região mais nova onde iniciamos as operações."

A produção das cooperativas associadas deve crescer 5,6%, atingindo 5,6 milhões de sacas,
enquanto o fornecimento de produtores independentes deve aumentar 16,7%, chegando a 1,4 milhão.

Investimentos mínimos de R$ 58 milhões estão planejados para comportar o volume maior.
O setor cafeeiro conta atualmente com condições favoráveis, com a produção nacional crescendo
pelo terceiro ano consecutivo após a seca severa de 2020 e as geadas de 2021.

Na B3, contratos futuros de café para maio são negociados em torno de US$ 224 por saca,
representando uma valorização de 6,7% em doze meses. Internacionalmente, contratos com
vencimento em maio são cotados a US$ 1,8570 por libra-peso.

As cooperativas já venderam 82% da safra de 2023 e pré-venderam 18% da produção antecipada
de 2024. O superintendente comercial Luiz Fernando dos Reis destacou: "O café acima de
US$ 200 por saca já cobre nossos custos. Antecipar parte das vendas alivia a pressão sobre
os produtores."

Apesar das perspectivas positivas, as perturbações na cadeia de abastecimento decorrentes
dos conflitos europeus e dos ataques ao Mar Vermelho continuam afetando o setor, com atrasos
portuários persistentes.
""".strip()

# ---------------------------------------------------------------------------
# Sample excerpt from Sustainability Report 2025/2024 (Nimble PDF extraction)
# ---------------------------------------------------------------------------

SUSTAINABILITY_REPORT_EXCERPT = """
Cooxupé — Sustainability Report and Financial Statements 2025/2024

ABOUT THE REPORT (GRI 2-1, 2-2, 2-3, 2-5, 2-14)
The Regional Cooperative of Coffee Growers in Guaxupé Ltd. – Cooxupé publishes its third
Sustainability Report and Financial Statements, covering the period from January 1 to
December 31, 2025, contributing to the development of the organization's sustainability
agenda based on cooperative principles.

Cooxupé operates through business units including its headquarters in Guaxupé and hubs
in Southern Minas, Cerrado Mineiro, Matas de Minas, and the Média Mogiana region of São Paulo.
It exports green coffee to more than 50 countries across five continents.

MESSAGE FROM THE PRESIDENCY (GRI 2-22)
In a scenario of global transformations, planning, unity and strategic management reinforce
the strength of the cooperative model. The past year was marked by a challenging environment:
changes in international trade, tariff pressures, logistical instability, and economic
uncertainties demanded resilience above all.

Amid this context, Cooxupé maintained its trajectory of growth and strengthened its management,
expanding solutions that generate economic sustainability for both cooperative members and the
cooperative itself. We officially announced Cooxupé's entry into the grain market — corn and
soybeans — expanding the cooperative's business for families who produce multiple crops.

HIGHLIGHTS 2025
- Record volume received: 7 million coffee bags
- Investments of R$ 58 million in infrastructure and logistics
- Exports to 50+ countries, 5 continents
- Entry into grain market (corn and soybeans) announced
- Third consecutive year of production growth post-2021 frost

OPERATIONS
Cooxupé's core business is the receipt, classification, storage, and commercialization of
coffee from its cooperative members. It owns SMC Commercial and Coffee Export Company S.A.,
dedicated to specialty and certified coffees; Cooxupé Insurance Brokerage; and logistics
infrastructure spanning Minas Gerais and São Paulo states.

Coffee futures on B3 (May contract): ~US$ 224/bag (+6.7% YoY).
International benchmark (ICE, May expiry): US$ 1.8570/lb.

SUSTAINABILITY AGENDA
Cooxupé is aligned with GRI standards and UN Sustainable Development Goals. Key ESG focus
areas: soil management, water use, climate adaptation, emissions reduction, diversity and
inclusion, and community impact in rural Minas Gerais.
""".strip()


async def run_demo() -> None:
    client = SensoClient()

    print("=== Cooxupé Demo: Scaffolding KB ===")
    folder_map = await scaffold_kb(client)

    print("\n=== Ingesting InfoMoney article (Nimble source) ===")
    article_meta = FilingMetadata(
        ticker="COOXUPE",
        filing_type="NEWS",
        fiscal_year=2024,
        source_url=(
            "https://www.infomoney.com.br/business/"
            "cooxupe-se-prepara-para-receber-7-milhoes-de-sacas-de-cafe-em-2024/"
        ),
        language="pt-BR",
    )
    article_node = await ingest_filing(INFOMONEY_ARTICLE, article_meta, folder_map, client)
    print(f"  ✓ Ingested: {article_node.get('kb_node_id')} — {article_meta.document_title()}")

    print("\n=== Ingesting Sustainability Report excerpt (Nimble PDF extraction) ===")
    report_meta = FilingMetadata(
        ticker="COOXUPE",
        filing_type="SR",
        fiscal_year=2024,
        source_url="https://www.cooxupe.com.br/wp-content/uploads/2026/04/ENG_relatorio-web_revisado_completo_compressed.pdf",
        language="en",
    )
    report_node = await ingest_filing(SUSTAINABILITY_REPORT_EXCERPT, report_meta, folder_map, client)
    print(f"  ✓ Ingested: {report_node.get('kb_node_id')} — {report_meta.document_title()}")

    print("\n=== Sample search (orchestrator query) ===")
    query = "What is Cooxupe's coffee volume forecast and key investment plans?"
    print(f"Query: {query!r}\n")
    context = await search_for_brief(query, client=client)
    print(context)


if __name__ == "__main__":
    asyncio.run(run_demo())
