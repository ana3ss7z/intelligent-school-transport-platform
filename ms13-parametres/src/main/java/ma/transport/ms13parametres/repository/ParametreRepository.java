package ma.transport.ms13parametres.repository;

import ma.transport.ms13parametres.entity.Parametre;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ParametreRepository extends JpaRepository<Parametre, String> {

    /** Ordre d'affichage : par onglet, puis dans l'ordre du catalogue. */
    List<Parametre> findAllByOrderByGroupeAscOrdreAsc();

    List<Parametre> findByGroupeOrderByOrdreAsc(Parametre.Groupe groupe);
}
