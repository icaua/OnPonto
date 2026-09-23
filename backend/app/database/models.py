from datetime import date, datetime, time

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Empresa(Base, TimestampMixin):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    cnpj: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    prazo_compensacao_banco_horas_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feriado_entra_banco: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    funcionarios = relationship("Funcionario", back_populates="empresa", cascade="all, delete-orphan")
    competencias = relationship("Competencia", back_populates="empresa", cascade="all, delete-orphan")
    escalas = relationship("Escala", back_populates="empresa", cascade="all, delete-orphan")


class Escala(Base, TimestampMixin):
    __tablename__ = "escalas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    modo_apuracao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="carga_horaria"
    )

    jornada_seg_sex_horas: Mapped[float | None] = mapped_column(Float, nullable=True)
    jornada_sabado_horas: Mapped[float | None] = mapped_column(Float, nullable=True)

    horario_entrada_prevista: Mapped[time | None] = mapped_column(Time, nullable=True)
    horario_saida_almoco_prevista: Mapped[time | None] = mapped_column(Time, nullable=True)
    horario_retorno_almoco_prevista: Mapped[time | None] = mapped_column(Time, nullable=True)
    horario_saida_prevista: Mapped[time | None] = mapped_column(Time, nullable=True)

    regime_sabado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="nao_trabalha"
    )
    regime_domingo: Mapped[str] = mapped_column(
        String(20), nullable=False, default="nao_trabalha"
    )

    tolerancia_atraso_minutos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tolerancia_extra_minutos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tolerancia_intervalo_minutos: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    usa_banco_horas: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    empresa = relationship("Empresa", back_populates="escalas")
    funcionarios = relationship("Funcionario", back_populates="escala")


class Funcionario(Base, TimestampMixin):
    __tablename__ = "funcionarios"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_funcionario_empresa_codigo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    codigo: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    nome: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    cargo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_admissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_demissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    escala_id: Mapped[int | None] = mapped_column(
        ForeignKey("escalas.id"), nullable=True, index=True
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    empresa = relationship("Empresa", back_populates="funcionarios")
    escala = relationship("Escala", back_populates="funcionarios")
    marcacoes = relationship("MarcacaoPonto", back_populates="funcionario", cascade="all, delete-orphan")


class EventoCalendario(Base, TimestampMixin):
    __tablename__ = "eventos_calendario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(180), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    abrangencia: Mapped[str] = mapped_column(String(20), nullable=False)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    municipio: Mapped[str | None] = mapped_column(String(120), nullable=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True, index=True)
    recorrente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Competencia(Base, TimestampMixin):
    __tablename__ = "competencias"
    __table_args__ = (UniqueConstraint("empresa_id", "mes", "ano", name="uq_competencia_empresa_mes_ano"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="aberta")
    apuracao_fechada: Mapped[str | None] = mapped_column(Text, nullable=True)
    versao_fechamento: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    data_recebimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_fechamento: Mapped[date | None] = mapped_column(Date, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    empresa = relationship("Empresa", back_populates="competencias")
    arquivos = relationship("ArquivoRecebido", back_populates="competencia", cascade="all, delete-orphan")
    marcacoes = relationship("MarcacaoPonto", back_populates="competencia", cascade="all, delete-orphan")


class ArquivoRecebido(Base):
    __tablename__ = "arquivos_recebidos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    competencia_id: Mapped[int] = mapped_column(ForeignKey("competencias.id"), nullable=False, index=True)
    nome_original: Mapped[str] = mapped_column(String(255), nullable=False)
    caminho_arquivo: Mapped[str] = mapped_column(String(500), nullable=False)
    tipo_arquivo: Mapped[str] = mapped_column(String(30), nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    competencia = relationship("Competencia", back_populates="arquivos")
    marcacoes = relationship("MarcacaoPonto", back_populates="arquivo_origem")


class MarcacaoPonto(Base, TimestampMixin):
    __tablename__ = "marcacoes_ponto"
    __table_args__ = (
        UniqueConstraint(
            "funcionario_id",
            "data",
            name="uq_marcacao_funcionario_data",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    competencia_id: Mapped[int] = mapped_column(ForeignKey("competencias.id"), nullable=False, index=True)
    funcionario_id: Mapped[int] = mapped_column(ForeignKey("funcionarios.id"), nullable=False, index=True)
    data: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    entrada: Mapped[time | None] = mapped_column(Time, nullable=True)
    saida_almoco: Mapped[time | None] = mapped_column(Time, nullable=True)
    retorno_almoco: Mapped[time | None] = mapped_column(Time, nullable=True)
    saida: Mapped[time | None] = mapped_column(Time, nullable=True)
    status_dia: Mapped[str] = mapped_column(String(30), default="normal")
    origem: Mapped[str] = mapped_column(String(30), default="manual")
    conferido: Mapped[bool] = mapped_column(Boolean, default=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    batidas_originais: Mapped[str | None] = mapped_column(Text, nullable=True)
    historico_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    arquivo_origem_id: Mapped[int | None] = mapped_column(
        ForeignKey("arquivos_recebidos.id"), nullable=True, index=True
    )

    competencia = relationship("Competencia", back_populates="marcacoes")
    funcionario = relationship("Funcionario", back_populates="marcacoes")
    arquivo_origem = relationship("ArquivoRecebido", back_populates="marcacoes")

    @property
    def historico(self) -> list[dict]:
        import json
        return json.loads(self.historico_json) if self.historico_json else []

    @property
    def arquivo_origem_nome(self) -> str | None:
        return self.arquivo_origem.nome_original if self.arquivo_origem else None


class OcorrenciaFuncionario(Base, TimestampMixin):
    __tablename__ = "ocorrencias_funcionario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    funcionario_id: Mapped[int] = mapped_column(ForeignKey("funcionarios.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    hora_inicio: Mapped[time | None] = mapped_column(Time, nullable=True)
    hora_fim: Mapped[time | None] = mapped_column(Time, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    anexo_caminho: Mapped[str | None] = mapped_column(Text, nullable=True)
    anexo_nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    excluido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    historico_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    funcionario = relationship("Funcionario")

    @property
    def empresa_id(self) -> int:
        return self.funcionario.empresa_id

    @property
    def historico(self) -> list[dict]:
        import json
        return json.loads(self.historico_json) if self.historico_json else []


class HistoricoVinculoEscala(Base, TimestampMixin):
    __tablename__ = "historico_vinculo_escala"
    __table_args__ = (CheckConstraint("vigente_ate IS NULL OR vigente_ate >= vigente_desde"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    funcionario_id: Mapped[int] = mapped_column(ForeignKey("funcionarios.id"), nullable=False, index=True)
    escala_id: Mapped[int] = mapped_column(ForeignKey("escalas.id"), nullable=False, index=True)
    vigente_desde: Mapped[date] = mapped_column(Date, nullable=False)
    vigente_ate: Mapped[date | None] = mapped_column(Date, nullable=True)
    funcionario = relationship("Funcionario")
    escala = relationship("Escala")


class LancamentoBancoHoras(Base, TimestampMixin):
    __tablename__ = "lancamentos_banco_horas"
    __table_args__ = (
        CheckConstraint("natureza IN ('credito', 'debito')"),
        CheckConstraint("origem IN ('apuracao', 'ajuste_manual', 'folga_compensatoria')"),
        CheckConstraint("status IN ('ativo', 'estornado')"),
        CheckConstraint("minutos > 0"),
        CheckConstraint("origem != 'ajuste_manual' OR length(trim(observacao)) > 0 AND observacao IS NOT NULL"),
        CheckConstraint("origem = 'ajuste_manual' OR (competencia_origem_id IS NOT NULL AND versao_fechamento IS NOT NULL AND versao_fechamento > 0 AND escala_origem_id IS NOT NULL)"),
        CheckConstraint("natureza != 'credito' OR (data_vencimento IS NOT NULL AND prazo_compensacao_aplicado_dias IS NOT NULL AND prazo_compensacao_aplicado_dias > 0)"),
        UniqueConstraint("competencia_origem_id", "versao_fechamento", "funcionario_id", "data_referencia", "origem", "natureza", name="uq_banco_geracao_diaria"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    funcionario_id: Mapped[int] = mapped_column(ForeignKey("funcionarios.id"), nullable=False, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    competencia_origem_id: Mapped[int | None] = mapped_column(ForeignKey("competencias.id"), nullable=True, index=True)
    escala_origem_id: Mapped[int | None] = mapped_column(ForeignKey("escalas.id"), nullable=True)
    natureza: Mapped[str] = mapped_column(String(10), nullable=False)
    origem: Mapped[str] = mapped_column(String(30), nullable=False)
    minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_lancamento: Mapped[date] = mapped_column(Date, nullable=False)
    data_vencimento: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    prazo_compensacao_aplicado_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feriado_entra_banco_aplicado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="ativo", index=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    versao_fechamento: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estornado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    motivo_estorno: Mapped[str | None] = mapped_column(Text, nullable=True)
    funcionario = relationship("Funcionario")
    competencia_origem = relationship("Competencia")


class CompensacaoBancoHoras(Base, TimestampMixin):
    __tablename__ = "compensacoes_banco_horas"
    __table_args__ = (
        CheckConstraint("minutos > 0"),
        CheckConstraint("credito_id != debito_id"),
        CheckConstraint("status IN ('ativo', 'estornado')"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    credito_id: Mapped[int] = mapped_column(ForeignKey("lancamentos_banco_horas.id"), nullable=False, index=True)
    debito_id: Mapped[int] = mapped_column(ForeignKey("lancamentos_banco_horas.id"), nullable=False, index=True)
    minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="ativo")
    estornada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    motivo_estorno: Mapped[str | None] = mapped_column(Text, nullable=True)
