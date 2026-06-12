import pdfplumber

with pdfplumber.open("../test.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text(layout=True)
        print(text)

"""


















      Fig.4. Anodicandcathodicpolarizationcurveofstainlesssteelin0.5MH2SO4solutioninthepresenceandabsenceofES.

     Table1
     PotentiodynamicpolarizationdataforstainlesssteelintheabsenceandpresenceofESin0.5MH2SO4solution.
      Inhibitor bc(V/dec) ba(V/dec) Ecorr(V) icorr(A/cm2) Polarization Corrosion
      concentration(g)                     resistance(Ω) rate(mm/year)
      0         0.0335 0.0409 (cid:3)0.9393 0.0003 24.0910 2.8163
      2         1.9460 0.0596 (cid:3)0.8276 0.0002 121.440 1.5054
      4         0.0163 0.2369 (cid:3)0.8825 0.0001 42.121 0.9476
      6         0.3233 0.0540 (cid:3)0.8027 5.39E-05 373.180 0.4318
      8         0.1240 0.0556 (cid:3)0.5896 5.46E-05 305.650 0.3772
      10        0.0382 0.0086 (cid:3)0.5356 1.24E-05 246.080 0.0919
       Theplotofinhibitorconcentrationoverdegreeofsurfacecoverageversusinhibitorconcentration
     gives a straight line as shown in Fig. 5. The strong correlation reveals that egg shell adsorption on
     stainlesssurfacein0.5MH SO followLangmuiradsorptionisotherm.Figs.6–8showtheSEM/EDX
                    2 4
     surfacemorphologyanalysisofstainlesssteel.Figs.7and8aretheSEM/EDXimagesofthestainless
     steelspecimenswithoutandwithinhibitorafterweightlossexperimentinsulphuricacidmedium.
     The stainless steel surface corrosionproduct layer in the absence of inhibitor was porous and as a
     resultgivesnocorrosionprotection.WiththepresenceofES,corrosiondamagewasminimized,with
     anevidenceofESpresentonthemetalsurfaceasshowninFig.8.
                 12
                 10
                 8
                 6

                 4
                 2
                  2      4     6     8     10
               0/C
     454            O.Sanni,A.P.I.Popoola/DatainBrief22(2019)451–457
                                              C/0
                            Concentration (g)
                       Fig.5. LangmuiradsorptionisothermofES.
"""