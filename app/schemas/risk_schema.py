from datetime import datetime
from typing import List, Optional

from app.extensions import db
from app.models import risk_assessment


class RiskService:
    """
    Serviço para criação e gerenciamento de avaliações de risco (RiskAssessment).
    """

    @staticmethod
    def create_assessment(
        user_id: int,
        asset_id: int,
        vulnerability_id: int,
        risk_score: float,
        recommendation_id: Optional[int] = None
    ) -> risk_assessment:
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
        assessment = risk_assessment(
            created_by=user_id,
            asset_id=asset_id,
            vulnerability_id=vulnerability_id,
            recommendation_id=recommendation_id,
            risk_score=risk_score,
            created_at=datetime.utcnow()
        )
        db.session.add(assessment)
        db.session.commit()
        return assessment

    @staticmethod
    def list_assessments_for_asset(asset_id: int) -> List[risk_assessment]:
        """
        Retorna todas as avaliações de risco de um ativo específico.
        """
        return risk_assessment.query.filter_by(asset_id=asset_id).all()

    @staticmethod
    def list_assessments_for_user(user_id: int = None) -> List[risk_assessment]:
        """
        Retorna todas as avaliações de risco.
        REMOVIDO: Não filtra mais por usuário.
        """
        return risk_assessment.query.all()

    @staticmethod
    def get_assessment(assessment_id: int) -> risk_assessment:
        """
        Busca uma avaliação de risco pelo seu ID.

        Raises:
            ValueError: se não encontrar.
        """
        assessment = risk_assessment.query.get(assessment_id)
        if not assessment:
            raise ValueError(f"Avaliação de risco {assessment_id} não encontrada.")
        return assessment

    @staticmethod
    def update_assessment(assessment_id: int, **kwargs) -> risk_assessment:
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
        db.session.commit()
        return assessment

    @staticmethod
    def delete_assessment(assessment_id: int) -> None:
        """
        Remove uma avaliação de risco do banco.
        """
        assessment = RiskService.get_assessment(assessment_id)
        db.session.delete(assessment)
        db.session.commit()
