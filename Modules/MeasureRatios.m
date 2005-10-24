function handles = MeasureRatios(handles)

% Help for the Measure Ratios module:
% Category: Measurement
%
% This module can take any measurement produced by previous modules and
% calculate a ratio. Ratios can also be used to calculate other ratios and
% be used in ClassifyObjects.
%
% Feature Number:
% The feature number is the parameter from the chosen module (AreaShape,
% Intensity, Texture) which will be used for the filter. The following
% tables provide the feature numbers for each measurement made by the three
% modules:
%
% Area Shape:               Feature Number:
% Area                    |       1
% Eccentricity            |       2
% Solidity                |       3
% Extent                  |       4
% Euler Number            |       5
% Perimeter               |       6
% Form factor             |       7
% MajorAxisLength         |       8
% MinorAxisLength         |       9
%
% Intensity:                Feature Number:
% IntegratedIntensity     |       1
% MeanIntensity           |       2
% StdIntensity            |       3
% MinIntensity            |       4
% MaxIntensity            |       5
% IntegratedIntensityEdge |       6
% MeanIntensityEdge       |       7
% StdIntensityEdge        |       8
% MinIntensityEdge        |       9
% MaxIntensityEdge        |      10
% MassDisplacement        |      11
%
% Texture:                  Feature Number:
% AngularSecondMoment     |       1
% Contrast                |       2
% Correlation             |       3
% Variance                |       4
% InverseDifferenceMoment |       5
% SumAverage              |       6
% SumVariance             |       7
% SumEntropy              |       8
% Entropy                 |       9
% DifferenceVariance      |      10
% DifferenceEntropy       |      11
% InformationMeasure      |      12
% InformationMeasure2     |      13
% Gabor1x                 |      14
% Gabor1y                 |      15
% Gabor2x                 |      16
% Gabor2y                 |      17
% Gabor3x                 |      18
% Gabor3y                 |      19
%
% See also MEASUREIMAGEAREAOCCUPIED, MEASUREIMAGEINTENSITY,
% MEASUREOBJECTINTENSITY, MEASUREOBJECTAREASHAPE,
% MEASUREOBJECTTEXTURE, MEASURECORRELATION

% CellProfiler is distributed under the GNU General Public License.
% See the accompanying file LICENSE for details.
%
% Developed by the Whitehead Institute for Biomedical Research.
% Copyright 2003,2004,2005.
%
% Authors:
%   Anne Carpenter <carpenter@wi.mit.edu>
%   Thouis Jones   <thouis@csail.mit.edu>
%   In Han Kang    <inthek@mit.edu>
%   Ola Friman     <friman@bwh.harvard.edu>
%   Steve Lowe     <stevelowe@alum.mit.edu>
%   Joo Han Chang  <joohan.chang@gmail.com>
%   Colin Clarke   <colinc@mit.edu>
%   Mike Lamprecht <mrl@wi.mit.edu>
%   Susan Ma       <xuefang_ma@wi.mit.edu>
%
% $Revision: 1843 $

%%%%%%%%%%%%%%%%
%%% VARIABLES %%%
%%%%%%%%%%%%%%%%
drawnow

%%% Reads the current module number, because this is needed to find
%%% the variable values that the user entered.
CurrentModule = handles.Current.CurrentModuleNumber;
CurrentModuleNum = str2double(CurrentModule);

%textVAR01 = Which object would you like to use for the numerator (The option IMAGE currently only works with Correlation measurements)?
%choiceVAR01 = Image
%infotypeVAR01 = objectgroup
%inputtypeVAR01 = popupmenu
NumObjectName = char(handles.Settings.VariableValues{CurrentModuleNum,1});

%textVAR02 = Which category of measurements would you like to use?
%choiceVAR02 = AreaShape
%choiceVAR02 = Correlation
%choiceVAR02 = Intensity
%choiceVAR02 = Neighbors
%choiceVAR02 = Texture
%inputtypeVAR02 = popupmenu custom
NumMeasure = char(handles.Settings.VariableValues{CurrentModuleNum,2});

%textVAR03 = Which feature do you want to use? (Enter the feature number - see HELP for explanation)
%defaultVAR03 = 1
NumFeatureNumber = str2num(handles.Settings.VariableValues{CurrentModuleNum,3});

%textVAR04 = If using INTENSITY or TEXTURE measures, which image would you like to process?
%infotypeVAR04 = imagegroup
%inputtypeVAR04 = popupmenu
NumImage = char(handles.Settings.VariableValues{CurrentModuleNum,4});

%textVAR05 = Which object would you like to use for the denominator (The option IMAGE currently only works with Correlation measurements)?
%choiceVAR05 = Image
%infotypeVAR05 = objectgroup
%inputtypeVAR05 = popupmenu
DenomObjectName = char(handles.Settings.VariableValues{CurrentModuleNum,5});

%textVAR06 = Which category of measurements would you like to use?
%choiceVAR06 = AreaShape
%choiceVAR06 = Correlation
%choiceVAR06 = Intensity
%choiceVAR06 = Neighbors
%choiceVAR06 = Texture
%inputtypeVAR06 = popupmenu custom
DenomMeasure = char(handles.Settings.VariableValues{CurrentModuleNum,06});

%textVAR07 = Which feature do you want to use? (Enter the feature number - see HELP for explanation)
%defaultVAR07 = 1
DenomFeatureNumber = str2num(handles.Settings.VariableValues{CurrentModuleNum,7});

%textVAR08 = If using INTENSITY or TEXTURE measures, which image would you like to process?
%infotypeVAR08 = imagegroup
%inputtypeVAR08 = popupmenu
DenomImage = char(handles.Settings.VariableValues{CurrentModuleNum,8});

%%%VariableRevisionNumber = 3

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%% MAKE MEASUREMENTS & SAVE TO HANDLES STRUCTURE %%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
drawnow

SetBeingAnalyzed = handles.Current.SetBeingAnalyzed;

if strcmp(NumMeasure,'Intensity') || strcmp(NumMeasure,'Texture')
    NumMeasure = [NumMeasure, '_', NumImage];
end

if strcmp(DenomMeasure,'Intensity') || strcmp(DenomMeasure,'Texture')
    DenomMeasure = [DenomMeasure, '_', DenomImage];
end

% Get measurements
NumeratorMeasurements = handles.Measurements.(NumObjectName).(NumMeasure){SetBeingAnalyzed};
NumeratorMeasurements = NumeratorMeasurements(:,NumFeatureNumber);
DenominatorMeasurements = handles.Measurements.(DenomObjectName).(DenomMeasure){SetBeingAnalyzed};
DenominatorMeasurements = DenominatorMeasurements(:,DenomFeatureNumber);

if length(NumeratorMeasurements) ~= length(DenominatorMeasurements)
    error(['The specified object names ',NumObjectName,' and ',DenomObjectName,' in the MeasureRatios do not have the same object count.']);
end

try
NewFieldName = [NumObjectName,'_',NumMeasure(1),'_',num2str(NumFeatureNumber),'_dividedby_',DenomObjectName,'_',DenomMeasure(1),'_',num2str(DenomFeatureNumber)];
if isfield(handles.Measurements.(NumObjectName),'Ratios')
    OldPos = strmatch(NewFieldName,handles.Measurements.(NumObjectName).RatiosFeatures,'exact');
    if isempty(OldPos)
        handles.Measurements.(NumObjectName).RatiosFeatures(end+1) = {NewFieldName};
        handles.Measurements.(NumObjectName).Ratios{SetBeingAnalyzed}(:,end+1) = NumeratorMeasurements./DenominatorMeasurements;
    else
        handles.Measurements.(NumObjectName).Ratios{SetBeingAnalyzed}(:,OldPos) = NumeratorMeasurements./DenominatorMeasurements;
    end
else
    handles.Measurements.(NumObjectName).RatiosFeatures = {NewFieldName};
    handles.Measurements.(NumObjectName).Ratios{SetBeingAnalyzed}(:,1) = NumeratorMeasurements./DenominatorMeasurements;
end
end
%NewFieldNameFeatures = [NumObjectName,'_',NumMeasure(1),'_',num2str(NumFeatureNumber),'_dividedby_',DenomObjectName,'_',DenomMeasure(1),'_',num2str(DenomFeatureNumber),'Features'];
%handles.Measurements.(NumObjectName).(NewFieldName)(SetBeingAnalyzed) = {NumeratorMeasurements./DenominatorMeasurements};
%handles.Measurements.(NumObjectName).(NewFieldNameFeatures) = {NewFieldName};
%%%%%%%%%%%%%%%%%%%%%%
%%% DISPLAY RESULTS %%%
%%%%%%%%%%%%%%%%%%%%%%
drawnow
if SetBeingAnalyzed == handles.Current.StartingImageSet
    %%% The figure window display is unnecessary for this module, so the figure
    %%% window is closed the first time through the module.
    fieldname = ['FigureNumberForModule',CurrentModule];
    ThisModuleFigureNumber = handles.Current.(fieldname);
    if any(findobj == ThisModuleFigureNumber) == 1;
        close(ThisModuleFigureNumber);
    end
end