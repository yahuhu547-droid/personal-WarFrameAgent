"""紫卡武器名规范化测试。"""

from warframe_agent.chat import ChatAgent


class TestNormalizeRivenWeaponUrl:
    """_normalize_riven_weapon_url 应将变体武器名还原为基础版。"""

    def _make_agent(self):
        from warframe_agent.dictionary import ItemResolver
        from warframe_agent.chat import ChatAgent

        return ChatAgent(
            resolver=ItemResolver(),
            order_fetcher=lambda item_id: [],
            model_call=lambda prompt: "",
        )

    def _norm(self, agent, url):
        return agent._normalize_riven_weapon_url(url)

    def test_sancti_magistar_to_magistar(self):
        agent = self._make_agent()
        assert self._norm(agent, "sancti_magistar") == "magistar"

    def test_sancti_tigris_to_tigris(self):
        agent = self._make_agent()
        assert self._norm(agent, "sancti_tigris") == "tigris"

    def test_vaykor_hek_to_hek(self):
        agent = self._make_agent()
        assert self._norm(agent, "vaykor_hek") == "hek"

    def test_vaykor_sydon_to_sydon(self):
        agent = self._make_agent()
        assert self._norm(agent, "vaykor_sydon") == "sydon"

    def test_vaykor_marelok_to_marelok(self):
        agent = self._make_agent()
        assert self._norm(agent, "vaykor_marelok") == "marelok"

    def test_prisma_grakata_to_grakata(self):
        agent = self._make_agent()
        assert self._norm(agent, "prisma_grakata") == "grakata"

    def test_prisma_angstrum_to_angstrum(self):
        agent = self._make_agent()
        assert self._norm(agent, "prisma_angstrum") == "angstrum"

    def test_prisma_lenz_to_lenz(self):
        agent = self._make_agent()
        assert self._norm(agent, "prisma_lenz") == "lenz"

    def test_prisma_tetra_to_tetra(self):
        agent = self._make_agent()
        assert self._norm(agent, "prisma_tetra") == "tetra"

    def test_prisma_skana_to_skana(self):
        agent = self._make_agent()
        assert self._norm(agent, "prisma_skana") == "skana"

    def test_prisma_gorgon_to_gorgon(self):
        agent = self._make_agent()
        assert self._norm(agent, "prisma_gorgon") == "gorgon"

    def test_prisma_machete_to_machete(self):
        agent = self._make_agent()
        assert self._norm(agent, "prisma_machete") == "machete"

    def test_prisma_obex_to_obex(self):
        agent = self._make_agent()
        assert self._norm(agent, "prisma_obex") == "obex"

    def test_prisma_ohma_to_ohma(self):
        agent = self._make_agent()
        assert self._norm(agent, "prisma_ohma") == "ohma"

    def test_prisma_grinlok_to_grinlok(self):
        agent = self._make_agent()
        assert self._norm(agent, "prisma_grinlok") == "grinlok"

    def test_secura_lecta_to_lecta(self):
        agent = self._make_agent()
        assert self._norm(agent, "secura_lecta") == "lecta"

    def test_secura_penta_to_penta(self):
        agent = self._make_agent()
        assert self._norm(agent, "secura_penta") == "penta"

    def test_telos_akbolto_to_akbolto(self):
        agent = self._make_agent()
        assert self._norm(agent, "telos_akbolto") == "akbolto"

    def test_telos_boltace_to_boltace(self):
        agent = self._make_agent()
        assert self._norm(agent, "telos_boltace") == "boltace"

    def test_telos_boltor_to_boltor(self):
        agent = self._make_agent()
        assert self._norm(agent, "telos_boltor") == "boltor"

    def test_rakta_cernos_to_cernos(self):
        agent = self._make_agent()
        assert self._norm(agent, "rakta_cernos") == "cernos"

    def test_rakta_ballistica_to_ballistica(self):
        agent = self._make_agent()
        assert self._norm(agent, "rakta_ballistica") == "ballistica"

    def test_normal_weapon_unchanged(self):
        agent = self._make_agent()
        assert self._norm(agent, "strun") == "strun"
        assert self._norm(agent, "rubico") == "rubico"
        assert self._norm(agent, "hek") == "hek"
        assert self._norm(agent, "magistar") == "magistar"

    def test_uppercase_variant_normalized(self):
        agent = self._make_agent()
        assert self._norm(agent, "SANCTI_MAGISTAR") == "magistar"
        assert self._norm(agent, "VAYKOR_HEK") == "hek"
        assert self._norm(agent, "Prisma_Grakata") == "grakata"