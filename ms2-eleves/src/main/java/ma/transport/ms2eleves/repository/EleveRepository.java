package ma.transport.ms2eleves.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import ma.transport.ms2eleves.entity.Eleve;

public interface EleveRepository
        extends JpaRepository<Eleve, Long> {

    List<Eleve> findByParentId(Long parentId);
    List<Eleve> findByGroupeId(Long groupeId);
    List<Eleve> findByGroupeIdIsNull();
    List<Eleve> findByBusId(Long busId);
}