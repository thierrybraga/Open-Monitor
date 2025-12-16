from datetime import datetime
from typing import List, Optional

from app.extensions import db
from app.models.risk_assessment import RiskAssessment


class RiskService:
    """
    Serviço para criação e gerenciamento de avaliações de risco (RiskAssessment).
    """

    @staticmethod
    def create_assessment(
        user_id: int,
        asset_id: int,
        vulnerability_id: str,
        risk_score: float,
        recommendation_id: Optional[int] = None
    ) -> RiskAssessment:
        """
        Cria uma nova avaliação de risco vinculando ativo, vulnerabilidade e recomendação.

        Args:
            user_id: ID do usuário que cria a avaliação.
            asset_id: ID do ativo avaliado.
            vulnerability_id: ID da vulnerabilidade associada.
            risk_score: Valor numérico da avaliação de risco.
            recommendation_id: ID opcional de recomendação.

        Returns:
            Instância de RiskAssessment criada.
        """
        assessment = RiskAssessment(
            created_by=user_id,
            asset_id=asset_id,
            vulnerability_id=vulnerability_id,
            # recommendation_id não existe no modelo atual; parâmetro ignorado.
            risk_score=risk_score,
            created_at=datetime.utcnow()
        )
        try:
            db.session.add(assessment)
            db.session.commit()
            return assessment
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def list_assessments_for_asset(asset_id: int) -> List[RiskAssessment]:
        """
        Retorna todas as avaliações de risco de um ativo específico.
        """
        return db.session.query(RiskAssessment).filter_by(asset_id=asset_id).all()

    @staticmethod
    def list_assessments_for_user(user_id: int = None) -> List[RiskAssessment]:
        """
        Retorna todas as avaliações de risco.
        REMOVIDO: Não filtra mais por usuário.
        """
        return db.session.query(RiskAssessment).all()

    @staticmethod
    def get_assessment(assessment_id: int) -> RiskAssessment:
        """
        Busca uma avaliação de risco pelo seu ID.

        Raises:
            ValueError: se não encontrar.
        """
        assessment = db.session.get(RiskAssessment, assessment_id)
        if not assessment:
            raise ValueError(f"Avaliação de risco {assessment_id} não encontrada.")
        return assessment

    @staticmethod
    def update_assessment(assessment_id: int, **kwargs) -> RiskAssessment:
        """
        Atualiza campos de uma avaliação de risco.

        Args:
            **kwargs: atributos de RiskAssessment a serem atualizados.

        Returns:
            Instância atualizada de RiskAssessment.
        """
        assessment = RiskService.get_assessment(assessment_id)
        for key, value in kwargs.items():
            if hasattr(assessment, key):
                setattr(assessment, key, value)
        try:
            db.session.commit()
            return assessment
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def delete_assessment(assessment_id: int) -> None:
        """
        Remove uma avaliação de risco do banco.
        """
        assessment = RiskService.get_assessment(assessment_id)
        try:
            db.session.delete(assessment)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
