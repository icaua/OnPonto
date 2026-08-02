from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time, UniqueConstraint
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
    jornada_seg_sex_horas: Mapped[float] = mapped_column(Float, default=8)
    jornada_sabado_horas: Mapped[float] = mapped_column(Float, default=4)
    tolerancia_atraso_minutos: Mapped[int] = mapped_column(Integer, default=5)
    tolerancia_extra_minutos: Mapped[int] = mapped_column(Integer, default=10)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    funcionarios = relationship("Funcionario", back_populates="empresa", cascade="all, delete-orphan")
    competencias = relationship("Competencia", back_populates="empresa", cascade="all, delete-orphan")


class Funcionario(Base, TimestampMixin):
    __tablename__ = "funcionarios"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_funcionario_empresa_codigo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    codigo: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    nome: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    cargo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    jornada_especifica_seg_sex_horas: Mapped[float | None] = mapped_column(Float, nullable=True)
    jornada_especifica_sabado_horas: Mapped[float | None] = mapped_column(Float, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    empresa = relationship("Empresa", back_populates="funcionarios")
    marcacoes = relationship("MarcacaoPonto", back_populates="funcionario", cascade="all, delete-orphan")


class Competencia(Base, TimestampMixin):
    __tablename__ = "competencias"
    __table_args__ = (UniqueConstraint("empresa_id", "mes", "ano", name="uq_competencia_empresa_mes_ano"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="aberta")
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


class MarcacaoPonto(Base, TimestampMixin):
    __tablename__ = "marcacoes_ponto"
    __table_args__ = (UniqueConstraint("competencia_id", "funcionario_id", "data", name="uq_marcacao_comp_func_data"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    competencia_id: Mapped[int] = mapped_column(ForeignKey("competencias.id"), nullable=False, index=True)
    funcionario_id: Mapped[int] = mapped_column(ForeignKey("funcionarios.id"), nullable=False, index=True)
    data: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    entrada: Mapped[time | None] = mapped_column(Time, nullable=True)
    saida_almoco: Mapped[time | None] = mapped_column(Time, nullable=True)
    retorno_almoco: Mapped[time | None] = mapped_column(Time, nullable=True)
    saida: Mapped[time | None] = mapped_column(Time, nullable=True)
    status_dia: Mapped[str] = mapped_column(String(30), default="pendente")
    origem: Mapped[str] = mapped_column(String(30), default="manual")
    conferido: Mapped[bool] = mapped_column(Boolean, default=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    competencia = relationship("Competencia", back_populates="marcacoes")
    funcionario = relationship("Funcionario", back_populates="marcacoes")
